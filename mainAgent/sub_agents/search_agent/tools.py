import html
import re
import warnings
from urllib.parse import quote

import requests

warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


_DEV_QUERY_HINTS = {
    "ai",
    "api",
    "app",
    "claude",
    "cloud",
    "code",
    "coder",
    "coding",
    "devops",
    "framework",
    "github",
    "gitlab",
    "javascript",
    "library",
    "llm",
    "model",
    "npm",
    "openai",
    "package",
    "programming",
    "python",
    "react",
    "repo",
    "repository",
    "sdk",
    "skill",
    "skills",
    "tool",
    "tools",
    "typescript",
}


def _normalize_ddg_results(raw_results: list[dict]) -> list[dict]:
    results = []
    for result in raw_results:
        title = result.get("title", "").strip()
        url = result.get("href", "").strip()
        snippet = result.get("body", "").strip()
        if not title or not url:
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _search_duckduckgo(query: str, max_results: int) -> tuple[list[dict], str | None]:
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results, backend="auto"))
        return _normalize_ddg_results(raw_results), None
    except Exception as exc:
        return [], str(exc)


def _search_wikipedia(query: str, max_results: int) -> list[dict]:
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "utf8": 1,
                "format": "json",
                "srlimit": max_results,
            },
            headers={"User-Agent": "ChatNCT/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "").strip()
            if not title:
                continue
            snippet = re.sub(r"<.*?>", "", item.get("snippet", ""))
            results.append(
                {
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                    "snippet": html.unescape(snippet).strip(),
                }
            )
        return results
    except Exception:
        return []


def _looks_like_dev_query(query: str) -> bool:
    query_words = set(re.findall(r"[a-zA-Z0-9#+._-]+", query.lower()))
    return bool(query_words & _DEV_QUERY_HINTS)


def _search_github_repositories(query: str, max_results: int) -> list[dict]:
    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "per_page": max_results, "sort": "stars", "order": "desc"},
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "ChatNCT/1.0",
            },
            timeout=15,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        results = []
        for item in items:
            title = item.get("full_name", "").strip()
            url = item.get("html_url", "").strip()
            snippet = (item.get("description") or "").strip()
            if not title or not url:
                continue
            results.append({"title": title, "url": url, "snippet": snippet})
        return results
    except Exception:
        return []


def _dedupe_results(*result_groups: list[dict], limit: int) -> list[dict]:
    merged = []
    seen_urls = set()
    for group in result_groups:
        for result in group:
            url = result.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(result)
            if len(merged) >= limit:
                return merged
    return merged


def duckduckgo_search_tool(query: str, max_results: int = 5) -> dict:
    """Search the web and return the top results with resilient fallbacks."""
    dev_query = _looks_like_dev_query(query)
    ddg_results, ddg_error = _search_duckduckgo(query, max_results)
    github_results = _search_github_repositories(query, max_results) if dev_query else []
    wiki_results = _search_wikipedia(query, max_results) if (not ddg_results and not dev_query) else []

    if dev_query:
        results = _dedupe_results(ddg_results, github_results, wiki_results, limit=max_results)
    else:
        results = _dedupe_results(ddg_results, wiki_results, github_results, limit=max_results)

    if results:
        fallback_used = not ddg_results
        message = "Fallback sources used." if fallback_used else "DuckDuckGo results."
        return {
            "status": "success",
            "results": results,
            "message": message,
            "fallback_used": fallback_used,
            "duckduckgo_error": ddg_error,
        }

    error_message = ddg_error or "No search results were returned from any source."
    return {"status": "error", "error_message": error_message, "results": []}
