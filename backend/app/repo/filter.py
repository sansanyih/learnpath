"""File filtering and ranking for repository learning."""

from pathlib import Path

EXCLUDED_DIRS = {
    "node_modules",
    ".git",
    ".github",
    "dist",
    "build",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "coverage",
    "site-packages",
    "migrations",
}

ALLOWED_EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".rs",
    ".vue",
    ".sql",
    ".toml",
    ".yaml",
    ".yml",
    ".md",
    ".json",
    ".cfg",
    ".ini",
}

ENTRY_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "index.py",
    "index.ts",
    "index.js",
    "app.ts",
    "app.js",
    "main.ts",
    "main.js",
    "main.go",
    "dockerfile",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
}

KEYWORD_BONUS = ("core", "api", "router", "service", "model", "config", "client", "schema")


def pick_readme(paths: list[str]) -> str | None:
    candidates = [path for path in paths if Path(path).name.lower().startswith("readme")]
    if not candidates:
        return None
    return min(candidates, key=lambda path: (path.count("/"), len(path)))


def rank_files(items: list[dict], readme_text: str) -> list[dict]:
    """items: [{path, size}] from the git tree. Returns scored files, best first."""
    ranked: list[dict] = []
    for item in items:
        path = item.get("path", "")
        size = int(item.get("size") or 0)
        parts = path.split("/")
        if any(part in EXCLUDED_DIRS for part in parts[:-1]):
            continue
        if Path(path).suffix.lower() not in ALLOWED_EXT:
            continue
        if size <= 0 or size > 200_000:
            continue

        name = parts[-1].lower()
        score = 0
        if name in ENTRY_NAMES and size >= 800:
            score += 60
        if readme_text and (path in readme_text or name in readme_text.lower()):
            score += 40
        score += max(0, 24 - (len(parts) - 1) * 3)
        if 2_000 <= size <= 40_000:
            score += 15
        if name.endswith((".toml", ".yaml", ".yml", ".json")):
            score += 6
        if name.endswith(".md"):
            score += 4
        if any(keyword in path.lower() for keyword in KEYWORD_BONUS):
            score += 5
        if name.startswith("test") or "/test" in path:
            score -= 8
        if size < 800:
            score -= 30
        elif size < 1_500:
            score -= 10

        ranked.append({"path": path, "size": size, "score": score})

    ranked.sort(key=lambda item: (-item["score"], item["path"]))
    return ranked


def compact_file_list(files: list[dict], limit: int = 60) -> str:
    lines = [f"- {item['path']} ({item['size']} bytes)" for item in files[:limit]]
    return "\n".join(lines)
