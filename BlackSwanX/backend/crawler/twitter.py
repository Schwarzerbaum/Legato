"""Twitter/X scraper — uses Nitter instances for public tweets (no API key)."""
import httpx
from bs4 import BeautifulSoup


async def search_twitter(query: str, max_results: int = 30) -> list[dict]:
    """Search Twitter/X via Nitter (public, no auth needed).

    Nitter is a free Twitter frontend. We try multiple instances.
    Falls back gracefully if all instances are down.
    """
    nitter_instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.cz",
    ]

    posts = []
    for instance in nitter_instances:
        try:
            url = f"{instance}/search?f=tweets&q={query}"
            resp = httpx.get(url, timeout=15, follow_redirects=True,
                           headers={"User-Agent": "BlackSwanX/0.1"})
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for tweet in soup.select(".timeline-item"):
                content_el = tweet.select_one(".tweet-content")
                author_el = tweet.select_one(".username")
                stats_el = tweet.select_one(".tweet-stat")

                if content_el:
                    posts.append({
                        "platform": "twitter",
                        "content": content_el.get_text(strip=True)[:500],
                        "author": author_el.get_text(strip=True) if author_el else "unknown",
                        "url": "",
                        "engagement": 0,
                    })

                if len(posts) >= max_results:
                    break

            if posts:
                break  # Got results from this instance

        except Exception:
            continue

    return posts[:max_results]
