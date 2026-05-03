from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
from contextlib import suppress
from typing import Any, cast
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv


load_dotenv()
app = FastAPI()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "models/gemini-3.1-flash-live-preview")
INPUT_AUDIO_MIME = os.getenv("GEMINI_INPUT_AUDIO_MIME", "audio/pcm;rate=16000")

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
    if not os.environ.get("GEMINI_API_KEY"):
        await websocket.send_text("ERROR: Missing GEMINI_API_KEY")
        await websocket.close(code=1011)
        return

    live_config = cast(Any, {"response_modalities": ["AUDIO"]})
    receiver_task: asyncio.Task[None] | None = None

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=live_config) as session:
            receiver_task = asyncio.create_task(_forward_model_audio(session, websocket))

            while True:
                if receiver_task.done():
                    error = receiver_task.exception()
                    if error:
                        raise RuntimeError(f"Live receiver failed: {error}") from error
                    receiver_task = asyncio.create_task(_forward_model_audio(session, websocket))

                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    break

                audio_chunk = message.get("bytes")
                if audio_chunk is not None:
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=audio_chunk,
                            mime_type=INPUT_AUDIO_MIME,
                        )
                    )
                    continue

                text_message = message.get("text")
                if not text_message:
                    continue

                command = text_message.strip().upper()
                if command == "END_TURN":
                    await _end_audio_turn(session)
                elif command == "PING":
                    await websocket.send_text("PONG")
                else:
                    await session.send_client_content(
                        turns=[{"role": "user", "parts": [{"text": text_message}]}],
                        turn_complete=True,
                    )
    except WebSocketDisconnect:
        return
    except Exception as error:
        with suppress(Exception):
            await websocket.send_text(f"ERROR: {error}")
    finally:
        if receiver_task:
            receiver_task.cancel()
            with suppress(asyncio.CancelledError, APIError, Exception):
                await receiver_task


async def _forward_model_audio(session: Any, websocket: WebSocket) -> None:
    while True:
        try:
            async for response in session.receive():
                server_content = getattr(response, "server_content", None)
                model_turn = getattr(server_content, "model_turn", None)
                if not model_turn:
                    continue

                for part in getattr(model_turn, "parts", []) or []:
                    inline_data = getattr(part, "inline_data", None)
                    audio_data = getattr(inline_data, "data", None) if inline_data else None
                    if audio_data:
                        await websocket.send_bytes(audio_data)

            # After receive() completes (turn ends), wait briefly before attempting to receive again
            # This gives the session time to prepare for the next turn
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except APIError as error:
            if getattr(error, "status_code", None) == 1000:
                return
            raise
        except Exception:
            # Bubble up so outer loop can surface a clear websocket error.
            raise


async def _end_audio_turn(session: Any) -> None:
    try:
        await session.send_realtime_input(audio_stream_end=True)
    except TypeError:
        await session.send_client_content(turns=[], turn_complete=True)