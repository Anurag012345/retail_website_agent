from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class Settings:
    api_key: str


def _load_env_file() -> None:
    """Load variables from the repo-level .env file if present."""
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
    else:
        load_dotenv()


def _read_api_key(explicit: Optional[str] = None) -> str:
    candidate = explicit or os.getenv("TAVILY_API_KEY")
    if not candidate:
        raise RuntimeError(
            "Missing TAVILY_API_KEY. Set it in your environment or .env file."
        )
    return candidate


@lru_cache(maxsize=1)
def load_settings(*, api_key: Optional[str] = None) -> Settings:
    """Return validated settings, loading .env once and caching the result."""
    _load_env_file()
    return Settings(api_key=_read_api_key(api_key))
