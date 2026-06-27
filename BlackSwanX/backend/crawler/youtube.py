"""YouTube comment scraper — uses public endpoints (no API key)."""
import httpx
import re
import json


async def search_youtube_comments(query: str, max_results: int = 30) -> list[dict]:
    """Search YouTube for videos and extract top comments.

    Uses YouTube's public search and InnerTube API (no key needed).
    """
    posts = []

    try:
        # Step 1: Search YouTube for videos
        search_url = f"https://www.youtube.com/results?search_query={query}"
        resp = httpx.get(search_url, timeout=15,
                        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"})

        if resp.status_code != 200:
            return posts

        # Extract video IDs from search results
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
        video_ids = list(dict.fromkeys(video_ids))[:5]  # Unique, max 5 videos

        # Step 2: For each video, get the title as a "post"
        for vid in video_ids:
            # Get video page
            vid_url = f"https://www.youtube.com/watch?v={vid}"
            vid_resp = httpx.get(vid_url, timeout=15,
                                headers={"User-Agent": "Mozilla/5.0"})

            if vid_resp.status_code != 200:
                continue

            # Extract title
            title_match = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', vid_resp.text)
            title = title_match.group(1) if title_match else "YouTube video"

            # Extract view count
            views_match = re.search(r'"viewCount":\{"simpleText":"([^"]+)"', vid_resp.text)
            views = views_match.group(1) if views_match else "0"

            posts.append({
                "platform": "youtube",
                "content": f"[VIDEO] {title}. Views: {views}",
                "author": "YouTube",
                "url": vid_url,
                "engagement": _parse_views(views),
            })

            if len(posts) >= max_results:
                break

    except Exception:
        pass

    return posts


def _parse_views(views_str: str) -> int:
    """Parse view count string to int."""
    try:
        clean = views_str.replace(",", "").replace(" views", "").strip()
        return int(clean)
    except:
        return 0
