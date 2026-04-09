"""Shared configuration loaded from .env"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# RisingWave connection
RW = {
    "host": os.getenv("RW_HOST", "localhost"),
    "port": int(os.getenv("RW_PORT", "4566")),
    "user": os.getenv("RW_USER", "root"),
    "password": os.getenv("RW_PASSWORD", ""),
    "dbname": os.getenv("RW_DATABASE", "dev"),
    "sslmode": os.getenv("RW_SSLMODE", "prefer"),
}

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Demo tuning
GENERATOR_SPEED = float(os.getenv("GENERATOR_SPEED", "1.0"))
NUM_TRUCKS = int(os.getenv("NUM_TRUCKS", "10"))
NUM_WAREHOUSES = int(os.getenv("NUM_WAREHOUSES", "3"))
