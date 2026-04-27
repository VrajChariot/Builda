from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import io
import os
import re
import wave
from typing import Any, cast
from google import genai
from dotenv import load_dotenv


load_dotenv()
app = FastAPI()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.websocket("/talk-to-gemini")
async def talk_to_gemini(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                response_text = await asyncio.to_thread(generate_text_response, data)
                audio_bytes = await asyncio.to_thread(synthesize_audio, response_text)
                await websocket.send_bytes(audio_bytes)
            except Exception as error:
                await websocket.send_text(f"ERROR: {error}")
    except WebSocketDisconnect:
        return


def generate_text_response(user_input: str) -> str:
    model = "gemma-4-26b-a4b-it"
    system_prompt = (
        "You are a warm, thoughtful, and highly capable assistant. "
        "Your tone should feel natural, friendly, and human: conversational, clear, and never robotic. "
        "Respond like a smart, kind person who genuinely wants to help. "
        "\n\n"
        "Style and behavior:\n"
        "- Be friendly, calm, and encouraging.\n"
        "- Use plain language first, then add detail only when useful.\n"
        "- Show empathy when users are confused, stressed, or frustrated.\n"
        "- Keep answers practical and well-structured, with direct takeaways.\n"
        "- If a request is unclear, ask a short clarifying question instead of guessing.\n"
        "- Be honest about uncertainty and avoid making things up.\n"
        "\n"
        "You can use Google Search for up-to-date information. "
        "When you do, briefly mention the exact search query (or a close paraphrase) and why you ran it, "
        "so the user can follow your reasoning."
    )
    contents = user_input
    generate_content_config = {
        "system_instruction": [
            {"text": system_prompt},
        ],
    }

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=cast(Any, generate_content_config),
    )
    return response.text or "Sorry, I could not generate a response right now."


def synthesize_audio(text: str) -> bytes:
    model = "gemini-3.1-flash-tts-preview"
    contents = text
    generate_content_config = {
        "response_modalities": ["audio"],
        "speech_config": "charon",
    }

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=cast(Any, generate_content_config),
    )

    for candidate in (response.candidates if response else []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                mime_type = (getattr(inline_data, "mime_type", "") or "").lower()
                if "audio/l16" in mime_type:
                    sample_rate = parse_sample_rate(mime_type)
                    return pcm_to_wav(inline_data.data, sample_rate)
                return inline_data.data

    raise ValueError("No audio returned from Gemini")


def parse_sample_rate(mime_type: str) -> int:
    rate_match = re.search(r"rate=(\d+)", mime_type)
    if rate_match:
        return int(rate_match.group(1))
    return 24000


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()