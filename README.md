# Clipping Agent

Automated video clipping pipeline built with **FastAPI**, **yt-dlp**, **faster-whisper**, **OpenCV (YuNet face tracking)**, and **FFmpeg**. It turns long-form videos (multi-platform URLs or local video uploads) into vertical `9:16` (`1080x1920`) short-form clips with burned-in subtitles and platform-specific social media copy.

## Features
- **Multi-platform input**: Download videos via `yt-dlp` (YouTube, TikTok, Instagram, Facebook, X, Twitch, Vimeo, etc.) or upload local video files (`.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v`).
- **Speech-to-text**: Local transcription using `faster-whisper`.
- **Smart clip selection**: LLM-based viral moment selection (any OpenAI-compatible API) with automatic heuristic fallback when no LLM is configured.
- **9:16 Face-Tracked Rendering**: Dynamic horizontal crop tracking using OpenCV's YuNet face detector (`storage/yunet_face.onnx` is downloaded automatically on first run) + burned-in `.srt` subtitles via `ffmpeg`.
- **Social Media Copy & Review UI**: Generates tailored titles, descriptions/captions, and hashtags for **YouTube Shorts**, **TikTok**, and **Instagram Reels**, with an interactive web dashboard to preview, edit, approve, or reject clips.

## Prerequisites
- **Python 3.10+**
- **FFmpeg** installed and available in `PATH`

## Setup
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
```

Create `.env` from `.env.example`:
```bash
cp .env.example .env
```

Configure `.env` (optional LLM settings — supports **OpenAI**, **Google Gemini**, **Anthropic Claude**, **Groq**, **OpenRouter**, **DeepSeek**, **Mistral**, **Together**, **Ollama**, **LM Studio**, or any OpenAI-compatible endpoint; if left empty, heuristic selection and template copy are used):

```env
WHISPER_MODEL=small
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=int8

# Examples:
# LLM_PROVIDER=auto | openai | gemini | anthropic | groq | openrouter | deepseek | mistral | together | ollama | lmstudio
LLM_PROVIDER=gemini
LLM_API_KEY=your_api_key
LLM_BASE_URL=
LLM_MODEL=gemini-2.5-flash

# Local Ollama example (no API key needed):
# LLM_PROVIDER=ollama
# LLM_MODEL=llama3.1

DB_PATH=data/jobs.db
```

## Run
```bash
uvicorn app.api:app --reload
```
Open `http://127.0.0.1:8000` in your browser.

## API Endpoints
- `GET /` — Web dashboard
- `POST /jobs` — Start a job from a video URL
- `POST /jobs/upload` — Start a job from an uploaded local video file
- `GET /jobs` — List jobs
- `GET /jobs/{job_id}` — Get job status
- `GET /jobs/{job_id}/result` — Get completed job metadata
- `GET /jobs/{job_id}/files/{filename}` — Download/stream `.mp4` or `.srt`
- `PATCH /jobs/{job_id}/clips/{clip_id}` — Update clip review status (`pending_review` / `approved` / `rejected`), title, or social captions
