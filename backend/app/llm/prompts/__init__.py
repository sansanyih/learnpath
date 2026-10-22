"""Prompt loading helpers."""

from pathlib import Path

PROMPT_DIR = Path(__file__).parent


def load_prompt(name: str) -> tuple[str, str]:
    """Return (system, user_template) from a prompt file split by ---USER---."""
    text = (PROMPT_DIR / name).read_text(encoding="utf-8")
    system, _, user = text.partition("\n---USER---\n")
    return system.strip(), user.strip()
