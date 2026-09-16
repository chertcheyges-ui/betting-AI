import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
