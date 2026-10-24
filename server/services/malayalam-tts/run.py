#!/usr/bin/env python3
"""
Malayalam TTS Server (Piper Backend)
Compatible with OpenAI Speech API: POST /v1/audio/speech
"""

import os
import sys
from pathlib import Path

VENV_PYTHON = Path("/home/athira/iccc/dynamic/backend/venv/bin/python")
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    try:
        import piper
    except ImportError:
        # Re-exec with venv python containing piper-tts
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

import argparse
import io
import json
import subprocess
import wave
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
DEFAULT_PORT = 8001

VOICE_FILES = {
    "arjun": MODELS_DIR / "ml_IN-arjun-medium.onnx",
    "ml_IN-arjun-medium": MODELS_DIR / "ml_IN-arjun-medium.onnx",
    "meera": MODELS_DIR / "ml_IN-meera-medium.onnx",
    "ml_IN-meera-medium": MODELS_DIR / "ml_IN-meera-medium.onnx",
}

loaded_voices = {}

def ensure_models():
    """Ensure Arjun and Meera models are downloaded."""
    arjun_model = MODELS_DIR / "ml_IN-arjun-medium.onnx"
    meera_model = MODELS_DIR / "ml_IN-meera-medium.onnx"
    if not (arjun_model.exists() and meera_model.exists()):
        print("⬇️ Voice models missing, running get_voices.sh...")
        subprocess.run(["bash", str(BASE_DIR / "get_voices.sh")], cwd=BASE_DIR, check=True)

def load_voice(voice_name: str):
    """Load a Piper voice instance."""
    from piper import PiperVoice

    key = voice_name.strip()
    target_file = VOICE_FILES.get(key)
    if not target_file or not target_file.exists():
        # Fallback to meera if not found
        key = "ml_IN-meera-medium"
        target_file = VOICE_FILES[key]

    if key not in loaded_voices:
        print(f"📦 Loading Piper voice: {target_file.name}...")
        loaded_voices[key] = PiperVoice.load(str(target_file))
    return loaded_voices[key]

def synthesize_wav(text: str, voice_name: str = "meera") -> bytes:
    """Synthesize text into WAV byte buffer."""
    voice = load_voice(voice_name)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(voice.config.sample_rate)
        for chunk in voice.synthesize(text):
            wf.writeframes(chunk.audio_int16_bytes)
    return buf.getvalue()

class TTSHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/v1/models", "/models"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "object": "list",
                "data": [
                    {"id": "ml_IN-meera-medium", "object": "model", "owned_by": "rhasspy"},
                    {"id": "ml_IN-arjun-medium", "object": "model", "owned_by": "rhasspy"},
                    {"id": "tts-1", "object": "model", "owned_by": "user"},
                ]
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "default_voice": "meera", "voices": ["meera", "arjun"]}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/v1/audio/speech":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON body"}')
                return

            text = data.get("input", "").strip()
            voice_name = data.get("voice") or data.get("model") or "ml_IN-meera-medium"

            if not text:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing input text"}')
                return

            try:
                wav_bytes = synthesize_wav(text, voice_name)
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav_bytes)))
                self.end_headers()
                self.wfile.write(wav_bytes)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port: int = DEFAULT_PORT):
    ensure_models()
    # Preload default voice (Meera)
    load_voice("meera")

    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, TTSHandler)
    print("\n" + "=" * 60)
    print("  🔊 Malayalam TTS Server (Piper Engine)")
    print("=" * 60)
    print(f"  • Listening on    : http://0.0.0.0:{port}")
    print(f"  • Speech Endpoint : http://localhost:{port}/v1/audio/speech")
    print(f"  • Default Voice   : Meera (Female, ml_IN-meera-medium)")
    print("=" * 60)
    print("  Sample curl command:")
    print(f'  curl -X POST http://localhost:{port}/v1/audio/speech \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"input": "നമസ്കാരം, സുഖമാണോ?", "voice": "ml_IN-meera-medium"}\' \\')
    print('    --output output.wav')
    print("=" * 60 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopping TTS server...")
        httpd.server_close()
        print("✅ TTS server stopped.")

def test_speech(port: int = DEFAULT_PORT):
    ensure_models()
    print("🧪 Running local speech synthesis test (Meera voice)...")
    wav_bytes = synthesize_wav("നമസ്കാരം, സുഖമാണോ?", "meera")
    out_path = BASE_DIR / "test_output.wav"
    with open(out_path, "wb") as f:
        f.write(wav_bytes)
    print(f"✨ Test audio written to: {out_path} ({len(wav_bytes)} bytes)")

def main():
    parser = argparse.ArgumentParser(description="Malayalam TTS Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default: 8001)")
    parser.add_argument("--test", action="store_true", help="Run quick test synthesis")
    args = parser.parse_args()

    if args.test:
        test_speech(args.port)
    else:
        run_server(args.port)

if __name__ == "__main__":
    main()
