from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from .base import *

DEBUG = True
REFERENCE_PERSONA_CATALOGUE_ENABLED = True
