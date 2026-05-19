from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import sys
from pathlib import Path
from collections.abc import Iterator
from typing import Any, cast
from google import genai
from google.genai import types
from dotenv import load_dotenv
from cli_ui import ui_print
import time
import traceback
import re
import json

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


# Function declaration schema for web app code generation
generate_webapp_code_decl = {
    "name": "generate_webapp_code",
    "description": "Create an on-demand single-file web app (HTML with embedded CSS and JavaScript) based on user requirements.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_request": {
                "type": "string",
                "description": "The user's request describing the web app to build (e.g., 'Create a portfolio website', 'Build a calculator app').",
            },
        },
        "required": ["user_request"],
    },
}


@app.websocket("/talk-to-gemini")
async def talk_to_gemini(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    ui_print("INFO", "be.main", f"WebSocket connection accepted: {websocket.client}")
    try:
        while True:
            data = await websocket.receive_text()
            ui_print("INFO", "be.main", (f"Received text from client: {(data[:200] + '...') if len(data) > 200 else data}"))
            try:
                await asyncio.to_thread(
                    stream_response_chunks,
                    data,
                    websocket,
                    loop,
                )
                await websocket.send_text("DONE")
                ui_print("INFO", "be.main", (f"Sent DONE to client for input (truncated): {(data[:120] + '...') if len(data) > 120 else data}"))
            except Exception as error:
                ui_print("ERROR", "be.main", f"Error while streaming response chunks: {error}")
                traceback.print_exc()
                await websocket.send_text(f"ERROR: {error}")
    except WebSocketDisconnect:
        ui_print("INFO", "be.main", f"WebSocket disconnected: {websocket.client}")
        return

current_app_state = "Initial state: no web app built yet."

def extract_html_from_model_text(text: str) -> str:
    global current_app_state
    fenced = re.search(r"```(?:html)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        current_app_state = fenced.group(1).strip()
        return current_app_state
    current_app_state = text.strip()
    return current_app_state



def generate_webapp_code_impl(user_request: str) -> str:
    """Build a single-file web app (HTML with embedded CSS/JS) for a user request."""
    model = "gemma-4-26b-a4b-it"
    prompt = (
        "Create a complete single-file web app using HTML, CSS, and JavaScript for this request: "
        f"{user_request}\n\n"
        "If current_app_state is available and the user request is to modify or build upon an existing app, use current_app_state as the starting point and update the current code accordingly. "
        f"current_app_state: {current_app_state}"
        "Return only runnable HTML in one file. "
        "Include CSS inside <style> and JavaScript inside <script>. "
        "Do not include markdown fences, explanations, or extra text."
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    text = getattr(response, "text", "") or ""
    return extract_html_from_model_text(text)


def generate_text_response_stream(user_input: str, websocket: WebSocket, loop: asyncio.AbstractEventLoop) -> Iterator[str]:
    model = "gemma-4-26b-a4b-it"
    system_prompt = (
        "Your name is Friday. You are a helpful and empathetic voice assistant."
        "You are a voice assistant speaking aloud, not a text chat bot. "
        "Your tone should feel natural, warm, emotionally aware, and human. "
        "Respond like a thoughtful person speaking in one short spoken turn. "
        "\n\n"
        "Style and behavior:\n"
        "- Keep replies concise and spoken, usually 1 to 4 short sentences.\n"
        "- Sound natural and conversational, like you are talking with someone out loud.\n"
        "- Show empathy when the user sounds confused, stressed, excited, or frustrated.\n"
        "- Give the direct answer first, then a brief helpful follow-up only if needed.\n"
        "- If the request is unclear, ask one short clarifying question instead of guessing.\n"
        "- Be honest about uncertainty and avoid making things up.\n"
        "- Do not use markdown, headings, numbered lists, bullet points, checklists, or emphasis.\n"
        "- Do not use emojis, symbols meant for formatting, or text like **important**, #1, or #2.\n"
        "- Do not sound verbose, corporate, or scripted.\n"
        "\n"
        "You can use Google Search for up-to-date information. "
        "If you do, keep the mention brief and spoken, and do not include the raw search query unless it is truly useful."
        "\n\n"
        "Tool usage:\n"
        f"current_app_state: {current_app_state}\n"
        "- You have access to a tool named generate_webapp_code(user_request).\n"
        "- When the user asks Friday to build/create/make a web app/site/page with HTML/CSS/JS, call that tool.\n"
        "- If tool output is returned as HTML, return only that HTML."
        "- If current_app_state already contains an existing web app and the user asks to modify, update, or build upon it, call the tool and use that existing app as context.\n"
    )
    tools = types.Tool(function_declarations=cast(Any, [generate_webapp_code_decl]))
    generate_content_config = types.GenerateContentConfig(
        system_instruction=[{"text": system_prompt}],
        tools=[tools],
    )

    # Retry with exponential backoff for transient server errors
    max_attempts = 3
    backoff_sec = 1.0
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_input,
                config=generate_content_config,
            )

            ui_print("DEBUG", "be.main", (f"Starting text generation for input (truncated): {(user_input[:200] + '...') if len(user_input) > 200 else user_input}"))
            
            # Debug: check response structure
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None) or []
                part_types = [type(part).__name__ for part in parts]
                ui_print("DEBUG", "be.main", f"Response has {len(parts)} part(s): {part_types}")
            
            # Check if the model returned a function call (may be in any part, not just first)
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None) or []
                
                # Loop through all parts to find a function_call
                function_call = None
                for part in parts:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        function_call = fc
                        break
                
                if function_call:
                    fc_name = getattr(function_call, "name", None)
                    fc_args = getattr(function_call, "args", {}) or {}
                    # args can be a dict or a JSON string; handle both
                    if isinstance(fc_args, str):
                        try:
                            fc_args = json.loads(fc_args)
                        except Exception:
                            ui_print("WARNING", "be.main", "Failed to parse function_call.args as JSON; using raw string")
                            fc_args = {"user_request": fc_args}

                    ui_print("INFO", "be.main", f"Model invoked tool: {fc_name} id={getattr(function_call, 'id', None)}")

                    if fc_name == "generate_webapp_code":
                        user_request_arg = None
                        if isinstance(fc_args, dict):
                            user_request_arg = fc_args.get("user_request")
                        elif isinstance(fc_args, str):
                            user_request_arg = fc_args

                        if user_request_arg:
                            try:
                                future = asyncio.run_coroutine_threadsafe(
                                    websocket.send_text(
                                        json.dumps(
                                            {
                                                "type": "artifact_loading",
                                                "message": "Building your web app...",
                                            }
                                        )
                                    ),
                                    loop,
                                )
                                future.result()
                                ui_print("INFO", "be.main", "Sent artifact loading payload to FE")
                            except Exception:
                                ui_print("WARNING", "be.main", "Failed to send artifact loading payload")
                                traceback.print_exc()

                            ui_print("DEBUG", "be.main", f"Calling generate_webapp_code with request: {(user_request_arg[:120] + '...') if len(user_request_arg) > 120 else user_request_arg}")
                            html_result = generate_webapp_code_impl(user_request_arg)
                            if html_result:
                                ui_print("DEBUG", "be.main", f"Tool returned HTML ({len(html_result)} bytes)")
                                yield html_result
                                return

                    ui_print("WARNING", "be.main", f"Unknown tool invoked: {fc_name}")
                    return
            
            # If no function call, yield text response
            text = getattr(response, "text", None) or ""
            if text:
                preview = (text[:200] + "...") if len(text) > 200 else text
                ui_print("DEBUG", "be.main", f"Received text from model: {preview}")
                yield text
            else:
                ui_print("WARNING", "be.main", "No text and no function call in response; yielding empty")
            return
        except Exception as e:
            last_exc = e
            ui_print("WARNING", "be.main", f"Attempt {attempt}/{max_attempts}: failed to generate response: {e}")
            if attempt < max_attempts:
                sleep = backoff_sec * (2 ** (attempt - 1))
                ui_print("INFO", "be.main", f"Retrying in {sleep:.1f}s...")
                time.sleep(sleep)
            else:
                ui_print("ERROR", "be.main", "All attempts to generate response failed")
                traceback.print_exc()
                raise last_exc


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


def stream_response_chunks(user_input: str, websocket: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
    ui_print("INFO", "be.main", (f"Begin streaming response chunks for input (truncated): {(user_input[:120] + '...') if len(user_input) > 120 else user_input}"))

    try:
        generated_text = "".join(generate_text_response_stream(user_input, websocket, loop)).strip()
    except Exception as e:
        ui_print("ERROR", "be.main", f"Failed to create text generation stream: {e}")
        traceback.print_exc()
        try:
            asyncio.run_coroutine_threadsafe(websocket.send_text(f"ERROR: {e}"), loop).result()
        except Exception:
            ui_print("ERROR", "be.main", "Failed to send error to websocket")
            traceback.print_exc()
        return

    html_candidate = extract_html_from_model_text(generated_text)
    looks_like_html = bool(
        re.search(r"<\s*!doctype\s+html|<\s*html\b|<\s*body\b|<\s*script\b|<\s*style\b", html_candidate, flags=re.IGNORECASE)
    )

    if looks_like_html or html_candidate.startswith("<"):
        # Send structured artifact payload to the frontend including the LLM response
        payload = {
            "type": "Artifact",
            "Code": html_candidate,
            "response": generated_text,
        }
        try:
            future = asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps(payload)),
                loop,
            )
            future.result()
            ui_print("INFO", "be.main", "Sent web app code payload to FE")
            confirmation = "I built the web app and sent the code to your renderer."
            future = asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({"type": "assistant_delta", "text": confirmation})),
                loop,
            )
            future.result()
            try:
                audio_bytes = synthesize_chunk(confirmation)
                future = asyncio.run_coroutine_threadsafe(websocket.send_bytes(audio_bytes), loop)
                future.result()
            except Exception:
                ui_print("WARNING", "be.main", "Failed to synthesize/send build confirmation audio")
                traceback.print_exc()
            return
        except Exception as e:
            ui_print("ERROR", "be.main", f"Failed to send web app payload: {e}")
            traceback.print_exc()

    chunk_stream = stream_text_into_chunks(iter([generated_text]))

    sent_any_chunk = False
    for chunk_text in chunk_stream:
        if not chunk_text.strip():
            ui_print("DEBUG", "be.main", "Skipping empty chunk_text")
            continue
        chunk_text = normalize_voice_text(chunk_text)
        if not chunk_text:
            ui_print("DEBUG", "be.main", "Skipping normalized empty chunk_text")
            continue
        try:
            future = asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({"type": "assistant_delta", "text": chunk_text})),
                loop,
            )
            future.result()
        except Exception:
            ui_print("ERROR", "be.main", "Failed to send assistant text chunk")
            traceback.print_exc()
            continue
        ui_print("DEBUG", "be.main", (f"Synthesizing chunk (preview): {(chunk_text[:120] + '...') if len(chunk_text) > 120 else chunk_text}"))
        try:
            audio_bytes = synthesize_chunk(chunk_text)
            ui_print("DEBUG", "be.main", f"Synthesized chunk -> {len(audio_bytes)} bytes")
            future = asyncio.run_coroutine_threadsafe(websocket.send_bytes(audio_bytes), loop)
            future.result()
            ui_print("DEBUG", "be.main", f"Sent audio chunk to websocket (bytes={len(audio_bytes)})")
            sent_any_chunk = True
        except Exception:
            ui_print("ERROR", "be.main", "Failed to synthesize/send chunk_text")
            traceback.print_exc()

    if not sent_any_chunk:
        fallback_text = "Sorry, I could not generate a response right now."
        ui_print("WARNING", "be.main", "No chunks were sent; using fallback text")
        try:
            audio_bytes = synthesize_chunk(fallback_text)
            ui_print("INFO", "be.main", f"Synthesized fallback -> {len(audio_bytes)} bytes")
            future = asyncio.run_coroutine_threadsafe(websocket.send_bytes(audio_bytes), loop)
            future.result()
        except Exception:
            ui_print("ERROR", "be.main", "Failed to synthesize/send fallback audio")
            traceback.print_exc()
