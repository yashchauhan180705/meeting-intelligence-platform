"""FastAPI application entry point.

Configures CORS, lifespan (DB init + service wiring), and registers routers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_settings
from app.database import init_db
from app.routers import audio, conversations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, load AI models. Shutdown: cleanup."""
    settings = load_settings()
    logger.info("Initializing database...")
    await init_db()

    # Instantiate services (lazy-loaded models)
    from app.services.whisper_service import WhisperService
    from app.services.pyannote_service import PyannoteService
    from app.services.gemini_service import GeminiService

    ts = WhisperService(model_size=settings.whisper_model_size)
    ds = PyannoteService(hf_token=settings.huggingface_token)
    ss = GeminiService(api_key=settings.google_api_key)

    # Inject services into router
    conversations.configure(settings, ts, ds, ss)

    logger.info("Application ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Meeting Intelligence Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
settings = load_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(conversations.router)
app.include_router(audio.router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
