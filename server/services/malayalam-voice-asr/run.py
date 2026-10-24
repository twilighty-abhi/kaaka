#!/usr/bin/env python3
"""
Malayalam Voice ASR Server Runner
Repository: https://github.com/hxri-nxrxyxn/malayalam-voice-asr
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BIN_DIR = BASE_DIR / "bin"
MODELS_DIR = BASE_DIR / "models"
SERVER_BIN = BIN_DIR / "whisper-server"
SAMPLE_AUDIO = BASE_DIR / "record.mp3"

MODEL_URLS = {
    "ggml-base.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "ggml-small.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
}

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def find_best_model(preferred: str = None) -> Path:
    if preferred:
        p = Path(preferred)
        if not p.is_absolute():
            p = BASE_DIR / p
        if p.exists():
            return p
        print(f"⚠️ Specified model not found at: {preferred}, searching standard models...")

    # Priority: Sujithatz fine-tuned Malayalam model first, then standard fallbacks
    for model_name in ["ggml-model-q8_0.bin", "ggml-model-q5_0.bin", "ggml-model-q4_0.bin", "ggml-small.bin", "ggml-base.bin"]:
        p = MODELS_DIR / model_name
        if p.exists() and p.stat().st_size > 10_000_000:
            return p

    # If no working model exists, download base model automatically
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target = MODELS_DIR / "ggml-base.bin"
    print("⬇️ Downloading default whisper model (ggml-base.bin)...")
    cmd = ["curl", "-L", "-o", str(target), MODEL_URLS["ggml-base.bin"]]
    subprocess.run(cmd, check=True)
    return target

def test_transcription(port: int = 8080, audio_path: Path = SAMPLE_AUDIO) -> bool:
    if not audio_path.exists():
        print(f"❌ Audio file not found at: {audio_path}")
        return False

    url = f"http://127.0.0.1:{port}/inference"
    print(f"\n🔍 Testing transcription against {url} with {audio_path.name}...")

    cmd = [
        "curl", "-s", "-X", "POST", url,
        "-H", "Content-Type: multipart/form-data",
        "-F", f"file=@{audio_path}",
        "-F", "temperature=0.0",
        "-F", "language=ml",
        "-F", "response_format=json",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and res.stdout.strip():
            print("\n✨ Transcription Response:")
            print("-" * 50)
            print(res.stdout.strip())
            print("-" * 50)
            return True
        else:
            print(f"❌ Server returned error: {res.stderr or res.stdout}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def wait_for_server(port: int, timeout: int = 15) -> bool:
    start = time.time()
    url = f"http://127.0.0.1:{port}"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status in (200, 404, 405):
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def run_native(args):
    if not SERVER_BIN.exists():
        print(f"❌ whisper-server binary not found at {SERVER_BIN}")
        print("   Please ensure bin/whisper-server is present.")
        sys.exit(1)

    model_path = find_best_model(args.model)
    local_ip = get_local_ip()
    threads = args.threads or min(8, os.cpu_count() or 4)

    print("\n" + "=" * 65)
    print("  🎙️  Malayalam Voice ASR Server (Native Mode)")
    print("=" * 65)
    print(f"  • Model         : {model_path.name} ({model_path.stat().st_size // (1024*1024)} MB)")
    print(f"  • Web UI        : http://localhost:{args.port}")
    print(f"  • Network Web UI: http://{local_ip}:{args.port}")
    print(f"  • Inference API : http://localhost:{args.port}/inference")
    print(f"  • CPU Threads   : {threads}")
    print("=" * 65)
    print("  To test transcription from CLI:")
    print(f'  curl http://localhost:{args.port}/inference \\')
    print('    -H "Content-Type: multipart/form-data" \\')
    print(f'    -F "file=@{SAMPLE_AUDIO.name}" \\')
    print('    -F "temperature=0.0" \\')
    print(f'    -F "language={args.language}"')
    print("=" * 65 + "\n")

    cmd = [
        str(SERVER_BIN),
        "-m", str(model_path),
        "--host", args.host,
        "--port", str(args.port),
        "--public", str(BASE_DIR / "public"),
        "--convert",
        "-l", args.language,
        "-t", str(threads),
    ]

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{BIN_DIR}:{env.get('LD_LIBRARY_PATH', '')}"

    proc = subprocess.Popen(cmd, cwd=BASE_DIR, env=env)

    def cleanup(signum=None, frame=None):
        print("\n🛑 Stopping whisper-server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("✅ Server stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    if args.test:
        print("⏳ Waiting for server to initialize...")
        if wait_for_server(args.port):
            test_transcription(args.port, SAMPLE_AUDIO)
        else:
            print("❌ Server timed out while starting.")
        cleanup()

    try:
        proc.wait()
    except KeyboardInterrupt:
        cleanup()

def run_docker(args):
    # Optional Docker fallback if user specifically provides --docker
    import shutil
    docker_cmd = None
    if shutil.which("docker"):
        res = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if res.returncode == 0:
            docker_cmd = ["docker", "compose"]
        elif shutil.which("docker-compose"):
            docker_cmd = ["docker-compose"]

    if not docker_cmd:
        print("❌ Docker is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)

    compose_file = "docker-compose.cpu.yml"
    print(f"🐳 Running via Docker ({compose_file})...")
    cmd = docker_cmd + ["-f", compose_file, "up", "--build"]
    try:
        subprocess.run(cmd, cwd=BASE_DIR)
    except KeyboardInterrupt:
        print("\n🛑 Stopping docker container...")
        subprocess.run(docker_cmd + ["-f", compose_file, "down"], cwd=BASE_DIR)

def main():
    parser = argparse.ArgumentParser(description="Malayalam Voice ASR Server")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--model", type=str, default=None, help="Path to ggml model file (e.g. models/ggml-base.bin)")
    parser.add_argument("-l", "--language", type=str, default="ml", help="Language code (default: ml)")
    parser.add_argument("-t", "--threads", type=int, default=None, help="Number of CPU threads")
    parser.add_argument("--test", action="store_true", help="Start server, test with sample audio, and output result")
    parser.add_argument("--docker", action="store_true", help="Run via Docker container instead of native binary")
    args = parser.parse_args()

    os.chdir(BASE_DIR)

    if args.docker:
        run_docker(args)
    else:
        run_native(args)

if __name__ == "__main__":
    main()
