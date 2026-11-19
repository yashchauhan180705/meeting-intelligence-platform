# Meeting & Debate Intelligence Platform

A full-stack, local-first intelligence platform that transcribes, diarizes, analyzes, and summarizes meetings and debates with speaker-attribution, synchronized timeline playback, and AI-generated insights.

---

## Features

- **🎙️ Speech Transcription**: Fast local speech-to-text using `faster-whisper` (CTranslate2).
- **👥 Speaker Diarization**: Multi-speaker identification and interval tracking using `pyannote.audio 3.1`.
- **⏱️ Synchronized Timeline**: Interactive playback bar that syncs audio with the transcript and highlights active speakers.
- **📊 Speaker Analytics**: Automatic talk-time percentage, turn count, average turn length, and interruption detection.
- **🧠 AI Summarization**: Executive overview, key takeaways, action items with owners, and structured debate claims via Google Gemini API.
- **✏️ Editable Transcripts**: Rename speakers and edit transcript segments directly in the browser; updates propagate everywhere instantly.
- **📁 Local & Private**: Audio files and transcript data are stored locally in SQLite (`aiosqlite`) — zero external database configuration required.
- **💾 Multi-Format Export**: Export conversations as formatted text (`.txt`) or complete structured data (`.json`).

---

## Tech Stack

- **Frontend**: Next.js 16 (App Router, Turbopack), React 19, TypeScript
- **Backend**: FastAPI, Uvicorn, Python 3.11
- **AI / ML**: `faster-whisper`, `pyannote.audio`, `torch`, `google-generativeai`
- **Database**: SQLite (`aiosqlite`)

---

## Quickstart Guide

### 1. Backend Setup

```bash
cd backend

# Create & activate a Python 3.11 virtual environment
uv venv .venv --python 3.11
# Or: python -m venv .venv

# Windows activation:
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:
```env
HUGGINGFACE_TOKEN=your_huggingface_token_here
GOOGLE_API_KEY=your_google_ai_studio_key_here
AUDIO_STORAGE_PATH=./audio_files
MAX_UPLOAD_BYTES=26214400
LOW_CONFIDENCE_THRESHOLD=0.5
WHISPER_MODEL_SIZE=small
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Start the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```
- API Health Check: `http://localhost:8000/health`
- Swagger Documentation: `http://localhost:8000/docs`

---

### 2. Frontend Setup

```bash
cd frontend

# Install Node dependencies
npm install

# Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Project Structure

```
my-antigravity-app/
├── backend/
│   ├── app/
│   │   ├── lib/              # Core algorithms (analytics, merger, validation)
│   │   ├── routers/          # FastAPI endpoints (conversations, audio)
│   │   ├── services/         # Whisper, Pyannote, and Gemini service adapters
│   │   ├── config.py         # Application settings
│   │   ├── database.py       # SQLite connection & schema initialization
│   │   ├── main.py           # FastAPI entrypoint
│   │   └── pipeline.py       # Orchestration pipeline
│   ├── tests/                # Unit and integration test suites
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Backend environment template
├── frontend/
│   ├── app/                  # Next.js App Router (UI & layout)
│   ├── lib/                  # Browser recording & audio sync utilities
│   ├── package.json          # Frontend dependencies
│   └── .env.local.example    # Frontend environment template
├── specs/                    # Project specifications and architecture contracts
└── README.md
```

---

## License

MIT License.
