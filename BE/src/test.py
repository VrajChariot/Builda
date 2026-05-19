from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import sys
import re
import json
import time
import traceback
from pathlib import Path
from collections.abc import Iterator
from typing import Any, cast
from google import genai
from dotenv import load_dotenv
from cli_ui import ui_print

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from kokoro_tts import stream_text_into_chunks, synthesize_chunk

load_dotenv()
app = FastAPI()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

ui_print("INFO", "be.main", f"Starting BE app; GEMINI_API_KEY set={bool(os.environ.get('GEMINI_API_KEY'))}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Build intent detection ────────────────────────────────────────────────────
BUILD_INTENT_RE = re.compile(
    r'\b(build|create|make|generate|write)\b.{0,80}'
    r'\b(app|page|ui|component|todo|form|game|calculator|dashboard|tool|widget|site|website)\b',
    re.IGNORECASE
)


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/talk-to-gemini")
async def talk_to_gemini(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    ui_print("INFO", "be.main", f"WebSocket connection accepted: {websocket.client}")
    try:
        while True:
            data = await websocket.receive_text()
            ui_print("INFO", "be.main", f"Received: {(data[:200] + '...') if len(data) > 200 else data}")
            try:
                await asyncio.to_thread(
                    handle_request,
                    data,
                    websocket,
                    loop,
                )
                await websocket.send_text("DONE")
                ui_print("INFO", "be.main", "Sent DONE to client")
            except Exception as error:
                ui_print("ERROR", "be.main", f"Error handling request: {error}")
                traceback.print_exc()
                await websocket.send_text(f"ERROR: {error}")
    except WebSocketDisconnect:
        ui_print("INFO", "be.main", f"WebSocket disconnected: {websocket.client}")
        return


def handle_request(
    user_input: str,
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Single entry point — LLM decides voice vs artifact based on system prompt."""
    ui_print("INFO", "be.main", f"Handling request: {user_input[:120]}")

    # Use streaming to get the response
    text_stream = generate_text_response_stream(user_input)

    # Buffer the start to detect if it's JSON (artifact) or plain text (voice)
    buffer = ""
    is_artifact = None  # None = not yet determined
    artifact_threshold = 10  # chars to buffer before deciding

    full_response = ""
    text_chunks_for_voice = []

    for delta in text_stream:
        full_response += delta

        if is_artifact is None and len(full_response) >= artifact_threshold:
            stripped = full_response.lstrip()
            is_artifact = stripped.startswith("{")
            ui_print("INFO", "be.main", f"Response type detected: {'artifact' if is_artifact else 'voice'}")

        if is_artifact is False:
            # Voice mode — stream chunks as they arrive
            # Re-use existing chunk streaming logic
            break

    if is_artifact is True:
        # Collect remaining stream
        for delta in text_stream:
            full_response += delta

        # Parse and handle artifact
        raw = full_response.strip()
        raw = re.sub(r'^```json\s*|^```\s*|```\s*$', '', raw, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(raw)
            speech = parsed.get("speech", "Here's what I built for you.")
            code = parsed.get("code", "")
        except json.JSONDecodeError:
            ui_print("WARNING", "be.main", "JSON parse failed — treating as raw HTML")
            speech = "Here's what I built for you."
            code = raw

        if code:
            ui_print("INFO", "be.main", f"Sending artifact ({len(code)} chars)")
            _send_text_sync(websocket, loop, json.dumps({
                "type": "artifact",
                "code": code,
            }))

        speech = normalize_voice_text(speech)
        if speech:
            try:
                audio_bytes = synthesize_chunk(speech)
                _send_bytes_sync(websocket, loop, audio_bytes)
            except Exception:
                ui_print("ERROR", "be.main", "Failed to synthesize artifact speech")
                traceback.print_exc()

    else:
        # Voice mode — feed full_response + remaining stream into chunk pipeline
        def combined_stream():
            yield full_response
            for delta in text_stream:
                yield delta

        chunk_stream = stream_text_into_chunks(combined_stream())
        sent_any = False

        for chunk_text in chunk_stream:
            if not chunk_text.strip():
                continue
            chunk_text = normalize_voice_text(chunk_text)
            if not chunk_text:
                continue

            _send_text_sync(websocket, loop, json.dumps({
                "type": "assistant_delta",
                "text": chunk_text,
            }))

            try:
                audio_bytes = synthesize_chunk(chunk_text)
                _send_bytes_sync(websocket, loop, audio_bytes)
                sent_any = True
            except Exception:
                ui_print("ERROR", "be.main", "Failed to synthesize chunk")
                traceback.print_exc()

        if not sent_any:
            fallback = "Sorry, I could not generate a response right now."
            try:
                audio_bytes = synthesize_chunk(fallback)
                _send_bytes_sync(websocket, loop, audio_bytes)
            except Exception:
                ui_print("ERROR", "be.main", "Fallback synthesis failed")
                traceback.print_exc()


# ── Artifact handler ──────────────────────────────────────────────────────────
def handle_artifact_request(
    user_input: str,
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
) -> None:
    ui_print("INFO", "be.main", f"Handling artifact request: {user_input[:120]}")

    artifact_prompt = (
        f"User request: {user_input}\n\n"
        "Return a JSON object with EXACTLY this structure and nothing else:\n"
        '{"speech": "one or two natural spoken sentences describing what you built", '
        '"code": "complete self-contained single-file HTML with CSS and JS inline"}\n\n'
        "Rules for code:\n"
        "- Must be fully self-contained, no external CDN links, no imports\n"
        "- Must work immediately when rendered in an iframe srcdoc\n"
        "- Include pleasant styling, not bare HTML\n"
        "- Must be functional, not a placeholder\n\n"
        "Rules for speech:\n"
        "- Sound natural and conversational, like you are speaking aloud\n"
        "- Do not use markdown or lists\n\n"
        "CRITICAL: Return ONLY the raw JSON object. No backticks, no markdown, no explanation."
    )

    try:
        response = client.models.generate_content(
            model="gemma-4-26b-a4b-it",
            contents=artifact_prompt,
            config=cast(Any, {
                "system_instruction": [{"text": "You are a helpful assistant that builds web apps."}],
            }),
        )
        raw = (response.text or "").strip()
        ui_print("DEBUG", "be.main", f"Raw artifact response: {raw[:200]}")
    except Exception as e:
        ui_print("ERROR", "be.main", f"Artifact LLM call failed: {e}")
        traceback.print_exc()
        _send_text_sync(websocket, loop, f"ERROR: {e}")
        return

    # Strip accidental backticks
    raw = re.sub(r'^```json\s*|^```\s*|```\s*$', '', raw, flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(raw)
        speech = parsed.get("speech", "Here's what I built for you.")
        code = parsed.get("code", "")
    except json.JSONDecodeError:
        ui_print("WARNING", "be.main", "JSON parse failed — treating response as raw HTML")
        speech = "Here's what I built for you."
        code = raw

    # Send artifact to frontend first so it renders immediately
    if code:
        ui_print("INFO", "be.main", f"Sending artifact ({len(code)} chars)")
        _send_text_sync(websocket, loop, json.dumps({
            "type": "artifact",
            "code": code,
        }))
    else:
        ui_print("WARNING", "be.main", "No code in artifact response")

    # Speak the description
    speech = normalize_voice_text(speech)
    if speech:
        try:
            audio_bytes = synthesize_chunk(speech)
            _send_bytes_sync(websocket, loop, audio_bytes)
            ui_print("INFO", "be.main", f"Sent artifact speech audio ({len(audio_bytes)} bytes)")
        except Exception as e:
            ui_print("ERROR", "be.main", f"Failed to synthesize artifact speech: {e}")
            traceback.print_exc()


# ── Conversational streaming ──────────────────────────────────────────────────
def generate_text_response_stream(user_input: str) -> Iterator[str]:
    model = "gemma-4-26b-a4b-it"
    system_prompt = (
    "Your name is Friday. You are a helpful, empathetic voice assistant that can also build web apps on demand.\n\n"
    
    "You have two modes:\n\n"
    
    "VOICE MODE (default):\n"
    "- Used for questions, conversations, advice, and general help.\n"
    "- Keep replies concise, 1 to 4 short spoken sentences.\n"
    "- Sound natural and conversational, like talking with someone out loud.\n"
    "- Show empathy when the user sounds confused, stressed, excited, or frustrated.\n"
    "- Give the direct answer first, then a brief follow-up only if needed.\n"
    "- If unclear, ask one short clarifying question instead of guessing.\n"
    "- Be honest about uncertainty, never make things up.\n\n"
    
    "BUILD MODE:\n"
    "- Triggered when the user asks you to build, create, make, generate, or show something visual.\n"
    "- Examples: 'build a todo app', 'make me a calculator', 'create a pomodoro timer', 'show me a budget tracker'.\n"
    "- In this case, respond ONLY with a JSON object in this exact format:\n"
    '  {"type": "artifact", "speech": "one or two natural spoken sentences", "code": "complete HTML"}\n'
    "- speech: what you say out loud about what you built. Natural and friendly, no markdown.\n"
    "- code: complete single-file HTML with all CSS and JS inline. No external dependencies. Must work in an iframe srcdoc immediately.\n"
    "- Include pleasant styling. Make it functional, not a placeholder.\n\n"
    
    "SHARED RULES:\n"
    "- Never use markdown, bullet points, headers, bold, or numbered lists in voice responses.\n"
    "- Never use emojis or symbols in voice responses.\n"
    "- Do not sound verbose, corporate, or scripted.\n"
    "- You can use Google Search for current info — mention it briefly and naturally.\n"
    "- When in BUILD MODE, return ONLY the raw JSON object. No backticks, no explanation outside the JSON."
)
    generate_content_config = {
        "system_instruction": [{"text": system_prompt}],
    }

    max_attempts = 3
    backoff_sec = 1.0
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response_stream = client.models.generate_content_stream(
                model=model,
                contents=user_input,
                config=cast(Any, generate_content_config),
            )
            ui_print("DEBUG", "be.main", f"Text stream started for: {user_input[:120]}")
            for response in response_stream:
                text = getattr(response, "text", None) or ""
                if text:
                    ui_print("DEBUG", "be.main", f"Token delta: {text[:80]}")
                    yield text
            return
        except Exception as e:
            last_exc = e
            ui_print("WARNING", "be.main", f"Attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                sleep = backoff_sec * (2 ** (attempt - 1))
                ui_print("INFO", "be.main", f"Retrying in {sleep:.1f}s...")
                time.sleep(sleep)
            else:
                ui_print("ERROR", "be.main", "All stream attempts failed")
                traceback.print_exc()
                raise last_exc


def stream_response_chunks(
    user_input: str,
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
) -> None:
    ui_print("INFO", "be.main", f"Streaming response for: {user_input[:120]}")
    try:
        text_stream = generate_text_response_stream(user_input)
    except Exception as e:
        ui_print("ERROR", "be.main", f"Failed to create text stream: {e}")
        traceback.print_exc()
        _send_text_sync(websocket, loop, f"ERROR: {e}")
        return

    chunk_stream = stream_text_into_chunks(text_stream)
    sent_any_chunk = False

    for chunk_text in chunk_stream:
        if not chunk_text.strip():
            continue
        chunk_text = normalize_voice_text(chunk_text)
        if not chunk_text:
            continue

        # Send transcript delta to frontend
        _send_text_sync(websocket, loop, json.dumps({
            "type": "assistant_delta",
            "text": chunk_text,
        }))

        # Synthesize and send audio
        ui_print("DEBUG", "be.main", f"Synthesizing: {chunk_text[:80]}")
        try:
            audio_bytes = synthesize_chunk(chunk_text)
            ui_print("DEBUG", "be.main", f"Synthesized {len(audio_bytes)} bytes")
            _send_bytes_sync(websocket, loop, audio_bytes)
            sent_any_chunk = True
        except Exception:
            ui_print("ERROR", "be.main", "Failed to synthesize chunk")
            traceback.print_exc()

    if not sent_any_chunk:
        fallback = "Sorry, I could not generate a response right now."
        ui_print("WARNING", "be.main", "No chunks sent — using fallback")
        try:
            audio_bytes = synthesize_chunk(fallback)
            _send_bytes_sync(websocket, loop, audio_bytes)
        except Exception:
            ui_print("ERROR", "be.main", "Fallback synthesis failed")
            traceback.print_exc()


# ── Helpers ───────────────────────────────────────────────────────────────────
def normalize_voice_text(text: str) -> str:
    text = re.sub(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(
        r"["
        r"\U0001F300-\U0001F5FF"
        r"\U0001F600-\U0001F64F"
        r"\U0001F680-\U0001F6FF"
        r"\U0001F700-\U0001F77F"
        r"\U0001F780-\U0001F7FF"
        r"\U0001F800-\U0001F8FF"
        r"\U0001F900-\U0001F9FF"
        r"\U0001FA00-\U0001FAFF"
        r"\u2600-\u26FF"
        r"\u2700-\u27BF"
        r"]",
        "",
        text,
    )
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _send_text_sync(
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
    text: str,
) -> None:
    try:
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(text), loop
        ).result()
    except Exception:
        ui_print("ERROR", "be.main", f"Failed to send text: {text[:80]}")
        traceback.print_exc()


def _send_bytes_sync(
    websocket: WebSocket,
    loop: asyncio.AbstractEventLoop,
    data: bytes,
) -> None:
    try:
        asyncio.run_coroutine_threadsafe(
            websocket.send_bytes(data), loop
        ).result()
    except Exception:
        ui_print("ERROR", "be.main", "Failed to send bytes")
        traceback.print_exc()