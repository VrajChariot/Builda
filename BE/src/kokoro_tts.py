import io
import re
import wave

import numpy as np
from kokoro import KPipeline
from datetime import datetime
import traceback
from cli_ui import ui_print


pipeline = KPipeline(lang_code="a")
VOICE = "af_sarah"
SPEED = 0.88
SAMPLE_RATE = 24000

# using ui_print from cli_ui for consistent CLI output

SENTENCE_BOUNDARY_RE = re.compile(r'[.!?]+(?:["\')\]]+)?(?=\s|$)')


def split_sentences(text: str) -> tuple[list[str], str]:
    sentences = []
    last_end = 0

    for match in SENTENCE_BOUNDARY_RE.finditer(text):
        sentence = text[last_end:match.end()].strip()
        if sentence:
            sentences.append(sentence)
        last_end = match.end()

    return sentences, text[last_end:].lstrip()




def group_text_into_chunks(text: str, sentences_per_chunk: int = 2) -> list[str]:
    sentences, remainder = split_sentences(text)
    if remainder.strip():
        sentences.append(remainder.strip())

    chunks = [
        " ".join(sentences[index : index + sentences_per_chunk])
        for index in range(0, len(sentences), sentences_per_chunk)
        if sentences[index : index + sentences_per_chunk]
    ]
    ui_print("DEBUG", "be.kokoro_tts", f"Grouped text into {len(chunks)} chunks (sentences={len(sentences)})")
    return chunks


def stream_text_into_chunks(text_stream, sentences_per_chunk: int = 2):
    pending_sentences = []
    buffer = ""

    for text_delta in text_stream:
        if not text_delta:
            continue

        buffer += text_delta
        complete_sentences, buffer = split_sentences(buffer)
        pending_sentences.extend(complete_sentences)

        while len(pending_sentences) >= sentences_per_chunk:
            chunk = " ".join(pending_sentences[:sentences_per_chunk])
            ui_print("DEBUG", "be.kokoro_tts", (f"Yielding chunk from stream (preview): {(chunk[:120] + '...') if len(chunk) > 120 else chunk}"))
            yield chunk
            pending_sentences = pending_sentences[sentences_per_chunk:]

    if buffer.strip():
        pending_sentences.append(buffer.strip())

    if pending_sentences:
        final = " ".join(pending_sentences)
        ui_print("DEBUG", "be.kokoro_tts", (f"Yielding final chunk from stream (preview): {(final[:120] + '...') if len(final) > 120 else final}"))
        yield final


def generate_chunk(text: str) -> np.ndarray | None:
    ui_print("DEBUG", "be.kokoro_tts", (f"Generating raw audio samples from Kokoro for text preview: {(text[:120] + '...') if len(text) > 120 else text}"))
    segments = []
    for _, _, audio in pipeline(text, voice=VOICE, speed=SPEED):
        try:
            arr = np.asarray(audio, dtype=np.float32).reshape(-1)
            segments.append(arr)
        except Exception:
            ui_print("ERROR", "be.kokoro_tts", "Failed to process audio segment from Kokoro")
            traceback.print_exc()
    if not segments:
        ui_print("WARNING", "be.kokoro_tts", (f"Kokoro returned no segments for text preview: {(text[:80] + '...') if len(text) > 80 else text}"))
        return None
    combined = np.concatenate(segments)
    ui_print("DEBUG", "be.kokoro_tts", f"Generated {combined.size} samples from Kokoro")
    return combined


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    clipped = np.asarray(audio, dtype=np.float32).reshape(-1)
    clipped = np.clip(clipped, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm16.tobytes())

    return buffer.getvalue()


def synthesize_chunk(text: str) -> bytes:
    ui_print("INFO", "be.kokoro_tts", (f"Synthesize chunk request (preview): {(text[:120] + '...') if len(text) > 120 else text}"))
    audio = generate_chunk(text)
    if audio is None:
        ui_print("ERROR", "be.kokoro_tts", (f"Kokoro did not generate audio for text (preview): {(text[:120] + '...') if len(text) > 120 else text}"))
        raise ValueError("Kokoro did not generate any audio")
    wav = audio_to_wav_bytes(audio)
    ui_print("INFO", "be.kokoro_tts", f"Synthesize complete: {len(wav)} bytes")
    return wav