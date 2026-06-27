"""DuckDuckGo search — free, no API key needed."""
from duckduckgo_search import DDGS
from datetime import datetime


async def search_web(query: str, max_results: int = 20) -> list[dict]:
    """Search DuckDuckGo for a topic. Returns normalized post dicts."""
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "platform": "web",
                    "author": r.get("source", ""),
                    "content": f"{r.get('title', '')}. {r.get('body', '')}",
                    "url": r.get("href", ""),
                    "engagement": 0,
                    "published_at": None,
                })
    except Exception as e:
        results.append({
            "platform": "web",
            "author": "search_error",
            "content": f"Search failed: {str(e)}",
            "url": "",
            "engagement": 0,
            "published_at": None,
        })
    return results


async def search_news(query: str, max_results: int = 20) -> list[dict]:
    """Search DuckDuckGo News."""
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "platform": "web",
                    "author": r.get("source", ""),
                    "content": f"{r.get('title', '')}. {r.get('body', '')}",
                    "url": r.get("url", ""),
                    "engagement": 0,
                    "published_at": r.get("date"),
                })
    except Exception:
        pass
    return results
