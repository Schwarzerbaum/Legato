"""Unified crawler — orchestrates all platform crawlers into a single pipeline."""
import asyncio
from backend.crawler.duckduckgo import search_web, search_news
from backend.crawler.reddit import search_reddit


async def crawl_all_platforms(query: str, max_per_platform: int = 50) -> list[dict]:
    """Crawl all available platforms in parallel and return unified results.

    Each result has: platform, author, content, url, engagement, published_at
    """
    tasks = [
        search_web(query, max_results=max_per_platform),
        search_news(query, max_results=max_per_platform),
        search_reddit(query, max_results=max_per_platform),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_posts = []
    for result in results:
        if isinstance(result, list):
            all_posts.extend(result)

    # Deduplicate by URL
    seen_urls = set()
    unique_posts = []
    for post in all_posts:
        url = post.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique_posts.append(post)

    return unique_posts


def platform_stats(posts: list[dict]) -> dict:
    """Get post counts per platform."""
    stats = {}
    for p in posts:
        platform = p.get("platform", "unknown")
        stats[platform] = stats.get(platform, 0) + 1
    return stats
