"""Shared configuration — reads from .env locally, st.secrets on Streamlit Cloud."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def _get(key: str, default: str = "") -> str:
    """Read from Streamlit secrets first (cloud), then env vars (local)."""
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


# RisingWave connection
RW = {
    "host": _get("RW_HOST", "localhost"),
    "port": int(_get("RW_PORT", "4566")),
    "user": _get("RW_USER", "root"),
    "password": _get("RW_PASSWORD", ""),
    "dbname": _get("RW_DATABASE", "dev"),
    "sslmode": _get("RW_SSLMODE", "prefer"),
}

# OpenRouter
OPENROUTER_API_KEY = _get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = _get("OPENROUTER_MODEL")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Demo tuning
GENERATOR_SPEED = float(_get("GENERATOR_SPEED", "1.0"))
NUM_TRUCKS = int(_get("NUM_TRUCKS", "10"))
NUM_WAREHOUSES = int(_get("NUM_WAREHOUSES", "3"))
