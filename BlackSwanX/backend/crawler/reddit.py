"""Reddit scraper — uses public JSON endpoints (no API key)."""
import aiohttp
from datetime import datetime

HEADERS = {
    "User-Agent": "BlackSwanX/0.1 (research; educational)"
}


async def search_reddit(query: str, max_results: int = 50) -> list[dict]:
    """Search Reddit for posts about a topic using public JSON API."""
    results = []
    url = f"https://www.reddit.com/search.json?q={query}&sort=relevance&limit={min(max_results, 100)}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return results
                data = await resp.json()

        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            results.append({
                "platform": "reddit",
                "author": d.get("author", "[deleted]"),
                "content": f"{d.get('title', '')}. {d.get('selftext', '')[:500]}",
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "engagement": d.get("score", 0) + d.get("num_comments", 0),
                "published_at": datetime.fromtimestamp(d.get("created_utc", 0)).isoformat() if d.get("created_utc") else None,
                "subreddit": d.get("subreddit", ""),
            })
    except Exception:
        pass

    return results[:max_results]


async def get_subreddit_posts(subreddit: str, sort: str = "hot", limit: int = 25) -> list[dict]:
    """Get posts from a specific subreddit."""
    results = []
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return results
                data = await resp.json()

        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            results.append({
                "platform": "reddit",
                "author": d.get("author", "[deleted]"),
                "content": f"{d.get('title', '')}. {d.get('selftext', '')[:500]}",
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "engagement": d.get("score", 0) + d.get("num_comments", 0),
                "published_at": datetime.fromtimestamp(d.get("created_utc", 0)).isoformat() if d.get("created_utc") else None,
                "subreddit": subreddit,
            })
    except Exception:
        pass

    return results
