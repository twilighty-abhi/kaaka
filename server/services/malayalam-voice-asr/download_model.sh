#!/bin/bash
set -e

# Model configuration
MODEL_URL="https://huggingface.co/sujithatz/ggml-whisper-medium-ml/resolve/main/ggml-model-q4_0.bin"
MODEL_FILE="models/ggml-model-q4_0.bin"

mkdir -p models

if [ -f "$MODEL_FILE" ]; then
    echo "✅ Model already exists: $MODEL_FILE"
    exit 0
fi

echo "⬇️  Downloading model (ggml-model-q4_0.bin)..."
if command -v aria2c &> /dev/null; then
    aria2c -x 4 -s 4 -o ggml-model-q4_0.bin -d models "$MODEL_URL"
else
    echo "⚠️  aria2c not found, falling back to curl..."
    curl -L "$MODEL_URL" -o "$MODEL_FILE"
fi

echo "✅ Download complete."
