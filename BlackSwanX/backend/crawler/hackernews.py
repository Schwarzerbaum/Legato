"""Hacker News scraper — uses official free API (no key needed)."""
import httpx


async def search_hackernews(query: str, max_results: int = 20) -> list[dict]:
    """Search Hacker News via Algolia API (free, no auth)."""
    posts = []
    try:
        url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={max_results}"
        resp = httpx.get(url, timeout=15)
        if resp.status_code != 200:
            return posts

        data = resp.json()
        for hit in data.get("hits", []):
            posts.append({
                "platform": "hackernews",
                "content": f"{hit.get('title', '')}. {hit.get('story_text', '')[:300] if hit.get('story_text') else ''}",
                "author": hit.get("author", ""),
                "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"),
                "engagement": hit.get("points", 0) + hit.get("num_comments", 0),
            })
    except Exception:
        pass

    return posts[:max_results]
