# Malayalam Voice ASR

An easy-to-deploy, Dockerized solution for offline Malayalam Automatic Speech Recognition (ASR). This project makes it simple for anyone to spin up a local speech-to-text server using the power of `whisper.cpp` and a fine-tuned Malayalam model.

## 🚀 Features

*   **Easy Setup:** Get running in minutes with Docker and a simple helper script.
*   **Lightweight & Fast:** Uses the optimized `whisper.cpp` backend.
*   **Web Interface:** Includes a clean, simple HTML interface for uploading and transcribing audio files.
*   **Optimized Model:** Pre-configured to use a quantized (q4_0) medium model for a good balance of speed and accuracy on consumer hardware.

## 🛠️ Quick Start

### Prerequisites

*   Docker & Docker Compose
*   `curl` (or `aria2c` for faster downloads)

### Running the Project

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hxri-nxrxyxn/malayalam-voice-asr.git
    cd malayalam-voice-asr
    ```

2.  **Download the Model:**
    Run the included script to fetch the fine-tuned Malayalam model (~430MB).
    ```bash
    ./download_model.sh
    ```

3.  **Start the Server:**
    ```bash
    docker compose up -d --build
    ```

4.  **Access the GUI:**
    Open your browser and navigate to [http://localhost:8080](http://localhost:8080).

## 🖥️ API Usage (Terminal)

You can also send transcription requests directly via the terminal using `curl`:

```bash
curl http://localhost:8080/inference \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/audio.mp3" \
  -F "temperature=0.0" \
  -F "language=ml"
```

## ❤️ Credits & Acknowledgements

This project stands on the shoulders of giants. A special thanks to:

*   **[sujithatz](https://huggingface.co/sujithatz)**: For providing the [ggml-whisper-medium-ml](https://huggingface.co/sujithatz/ggml-whisper-medium-ml) model on Hugging Face, which makes this specific implementation possible.
*   **[Thennal](https://thennal.com/)**: For their incredible work in the Malayalam computing space and for making projects like this a reality through their resources and community efforts.
*   **[ggerganov](https://github.com/ggerganov)**: For the amazing [whisper.cpp](https://github.com/ggerganov/whisper.cpp) project.
