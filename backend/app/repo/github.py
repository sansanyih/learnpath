"""GitHub REST client for public repository reading."""

import base64
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class RepoError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ParsedRepo:
    owner: str
    repo: str
    ref: str | None = None


def parse_repo_url(url: str) -> ParsedRepo:
    text = url.strip()
    if "github.com" not in text:
        raise RepoError("INVALID_REPO_URL", "请粘贴 github.com 上的仓库地址")
    try:
        rest = text.split("github.com/", 1)[1]
    except IndexError as exc:
        raise RepoError("INVALID_REPO_URL", "请粘贴完整的 GitHub 仓库地址") from exc

    parts = [part for part in rest.split("/") if part]
    if len(parts) < 2:
        raise RepoError("INVALID_REPO_URL", "地址里缺少 owner/repo")

    owner, repo = parts[0], parts[1].removesuffix(".git")
    ref = None
    if len(parts) >= 4 and parts[2] == "tree":
        ref = parts[3].split("?")[0].split("#")[0]
    return ParsedRepo(owner=owner, repo=repo, ref=ref)


class GitHubClient:
    def __init__(self) -> None:
        settings = get_settings()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = settings.github_token.strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url="https://api.github.com", timeout=40, headers=headers)

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None):
        response = await self._client.get(path, params=params)
        if response.status_code == 401:
            raise RepoError("GITHUB_TOKEN_INVALID", "GitHub token 无效或已过期")
        if response.status_code == 404:
            raise RepoError("REPO_NOT_FOUND", "仓库或分支不存在，或没有读取权限")
        if response.status_code == 403:
            if response.headers.get("x-ratelimit-remaining") == "0":
                raise RepoError("GITHUB_RATE_LIMIT", "GitHub 接口限流，请稍后再试")
            raise RepoError("GITHUB_FORBIDDEN", "GitHub 拒绝了请求，请检查 token 的 Contents 只读权限")
        response.raise_for_status()
        return response.json()

    async def repo(self, owner: str, repo: str) -> dict:
        return await self._get(f"/repos/{owner}/{repo}")

    async def tree(self, owner: str, repo: str, ref: str) -> dict:
        return await self._get(
            f"/repos/{owner}/{repo}/git/trees/{quote(ref, safe='')}",
            params={"recursive": "1"},
        )

    async def content(self, owner: str, repo: str, path: str, ref: str) -> str:
        data = await self._get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
        if isinstance(data, list):
            raise RepoError("NOT_A_FILE", f"{path} 不是文件")
        if data.get("encoding") == "base64":
            return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        return data.get("content", "")
