"""Paths and settings. Settings come from environment variables or a `.env` file in the repo root."""

import os
from pathlib import Path

ROOT = Path(os.environ.get("MP_ROOT") or Path(__file__).resolve().parents[2])
MATLAB_DIR = ROOT / "matlab"
WEB_DIR = ROOT / "web"
EXAMPLES_DIR = ROOT / "examples"
PROMPTS_DIR = ROOT / "prompts"

HINT_THRESHOLD = 5


def _load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_DOTENV = _load_dotenv()


def setting(name: str, default: str | None = None) -> str | None:
    """An environment variable wins over `.env`, which wins over the default."""
    return os.environ.get(name) or _DOTENV.get(name) or default


def work_dir() -> Path:
    return Path(setting("MP_WORK_DIR") or ROOT / "my-work")


def problems_dir() -> Path:
    return work_dir() / "problems"


def solutions_dir() -> Path:
    return work_dir() / "solutions"


def submissions_dir() -> Path:
    return work_dir() / "submissions"
