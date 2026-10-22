"""Keyless web search (DuckDuckGo HTML) and safe page fetching."""

import asyncio
import html
import ipaddress
import re
import socket
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import get_settings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _strip_tags(raw: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _decode_ddg_href(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target
    return href


def _parse_ddg(html_text: str, limit: int) -> list[dict]:
    titles = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html_text, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html_text, re.S)
    results: list[dict] = []
    for index, (href, title) in enumerate(titles):
        url = _decode_ddg_href(html.unescape(href))
        if not url.startswith(("http://", "https://")):
            continue
        snippet = _strip_tags(snippets[index]) if index < len(snippets) else ""
        results.append({"title": _strip_tags(title), "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


async def _tavily_search(query: str, limit: int, api_key: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": limit,
                    "search_depth": "basic",
                    "include_answer": False,
                },
            )
        if response.status_code != 200:
            return []
        results = []
        for item in response.json().get("results", [])[:limit]:
            results.append(
                {
                    "title": item.get("title", "")[:160],
                    "url": item.get("url", ""),
                    "snippet": (item.get("content") or "")[:400],
                }
            )
        return [item for item in results if item["url"]]
    except Exception:  # noqa: BLE001 - fall back to DDG
        return []


async def search_web(query: str, limit: int = 4) -> list[dict]:
    """Search via Tavily if configured, else DuckDuckGo's HTML endpoint."""
    query = query.strip()
    if not query:
        return []

    tavily_key = get_settings().tavily_api_key.strip()
    if tavily_key:
        results = await _tavily_search(query, limit, tavily_key)
        if results:
            return results

    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    try:
        async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
            resp = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
        if resp.status_code == 200:
            results = _parse_ddg(resp.text, limit)
            if results:
                return results
    except Exception:  # noqa: BLE001 - search is best effort
        pass

    try:
        async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
            resp = await client.get("https://lite.duckduckgo.com/lite/", params={"q": query})
        if resp.status_code != 200:
            return []
        links = re.findall(r'class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.S)
        snippets = re.findall(r'class="result-snippet"[^>]*>(.*?)</td>', resp.text, re.S)
        results = []
        for index, (href, title) in enumerate(links):
            url = _decode_ddg_href(html.unescape(href))
            if not url.startswith(("http://", "https://")):
                continue
            results.append(
                {
                    "title": _strip_tags(title),
                    "url": url,
                    "snippet": _strip_tags(snippets[index]) if index < len(snippets) else "",
                }
            )
            if len(results) >= limit:
                break
        return results
    except Exception:  # noqa: BLE001
        return []


def _is_public_host(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ToolError("BAD_URL", "无法解析这个域名") from exc
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


async def fetch_url(url: str) -> dict:
    """Fetch a public http(s) page and return title + plain text excerpt."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ToolError("BAD_URL", "只支持 http/https 链接")
    if not await asyncio.to_thread(_is_public_host, parsed.hostname):
        raise ToolError("BAD_URL", "不能访问内网或本机地址")

    headers = {"User-Agent": USER_AGENT}
    current = url
    async with httpx.AsyncClient(timeout=25, headers=headers, follow_redirects=False) as client:
        for _ in range(4):
            resp = await client.get(current)
            if resp.is_redirect:
                location = resp.headers.get("location", "")
                target = urlparse(location)
                if target.scheme not in {"http", "https"} or not target.hostname:
                    raise ToolError("BAD_URL", "重定向地址不合法")
                if not await asyncio.to_thread(_is_public_host, target.hostname):
                    raise ToolError("BAD_URL", "不能访问内网或本机地址")
                current = location
                continue
            if resp.status_code >= 400:
                raise ToolError("FETCH_FAILED", f"网页返回 {resp.status_code}")
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                raise ToolError("FETCH_FAILED", "这个链接不是网页")
            text = resp.text[:200_000]
            title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
            title = _strip_tags(title_match.group(1)) if title_match else current
            body = _strip_tags(text)
            return {"url": current, "title": title[:160], "text": body[:6000]}
    raise ToolError("FETCH_FAILED", "重定向次数过多")
