import vertexai
from vertexai.generative_models import GenerativeModel
import base64
import subprocess

# 🔹 Init Vertex (uses your ADC automatically)
vertexai.init(
    project="project-builda-ai-2004"
)

# 🔹 Load TTS model
model = GenerativeModel("gemini-2.5-flash-preview-tts")


def text_to_speech(text: str, filename: str = "output.wav"):
    response = model.generate_content(
        text,
        generation_config={
            "response_modalities": ["AUDIO"]
        }
    )

    audio_base64 = response.candidates[0].content.parts[0].inline_data.data
    audio_bytes = base64.b64decode(audio_base64)

    with open(filename, "wb") as f:
        f.write(audio_bytes)

    print(f"✅ Saved: {filename}")

    return filename


# 🔥 Quick test
file = text_to_speech("Hey Vraj, this is your AI speaking with natural voice.")

# 🔊 Play on Mac
subprocess.run(["afplay", file])