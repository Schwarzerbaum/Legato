"""German tax regulatory crawlers — BMF Schreiben, BFH Urteile, and practitioner commentary.

Zero API cost. Uses DuckDuckGo site-restricted search to crawl:
- bundesfinanzministerium.de (BMF circulars and guidance)
- bundesfinanzhof.de (Federal Fiscal Court rulings)
- haufe.de (practitioner tax commentary)

Returns normalized post dicts compatible with the BlackSwanX pipeline.
"""

from duckduckgo_search import DDGS
from datetime import datetime


def _search_site(site: str, query: str, platform: str, author: str,
                 max_results: int = 20) -> list[dict]:
    """Run a site-restricted DuckDuckGo search and return normalized results.

    Args:
        site: Domain to restrict search to (e.g. "bundesfinanzministerium.de").
        query: Search terms appended after the site: operator.
        platform: Platform label for normalized output.
        author: Author label for normalized output.
        max_results: Maximum number of results to return.

    Returns:
        List of normalized post dicts.
    """
    results = []
    search_query = f"site:{site} {query}"
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(search_query, max_results=max_results):
                title = r.get("title", "")
                body = r.get("body", "")
                content = f"{title}. {body}" if body else title
                results.append({
                    "platform": platform,
                    "author": author,
                    "content": content,
                    "url": r.get("href", ""),
                    "engagement": 0,
                    "published_at": None,
                })
    except Exception as e:
        results.append({
            "platform": platform,
            "author": "search_error",
            "content": f"Search failed for {site}: {str(e)}",
            "url": "",
            "engagement": 0,
            "published_at": None,
        })
    return results


# ------------------------------------------------------------------
# Public crawl functions
# ------------------------------------------------------------------

async def crawl_bmf_schreiben(query: str = "BMF Schreiben aktuell",
                               max_results: int = 20) -> list[dict]:
    """Crawl BMF (Bundesfinanzministerium) circulars and guidance letters.

    Searches bundesfinanzministerium.de for recent BMF Schreiben,
    Verwaltungsanweisungen, and tax guidance documents.

    Args:
        query: Search terms. Defaults to recent BMF circulars.
        max_results: Maximum results to return.

    Returns:
        List of normalized post dicts with platform="bmf".
    """
    return _search_site(
        site="bundesfinanzministerium.de",
        query=query,
        platform="bmf",
        author="BMF",
        max_results=max_results,
    )


async def crawl_bfh_urteile(query: str = "BFH Urteil aktuell",
                             max_results: int = 20) -> list[dict]:
    """Crawl BFH (Bundesfinanzhof) court rulings and decisions.

    Searches bundesfinanzhof.de for recent tax court decisions,
    Revisionen, and Beschluesse.

    Args:
        query: Search terms. Defaults to recent BFH rulings.
        max_results: Maximum results to return.

    Returns:
        List of normalized post dicts with platform="bfh".
    """
    return _search_site(
        site="bundesfinanzhof.de",
        query=query,
        platform="bfh",
        author="BFH",
        max_results=max_results,
    )


async def crawl_haufe_steuerrecht(query: str = "Steuerrecht aktuell",
                                   max_results: int = 15) -> list[dict]:
    """Crawl Haufe.de for practitioner tax commentary and analysis.

    Args:
        query: Search terms. Defaults to current tax law topics.
        max_results: Maximum results to return.

    Returns:
        List of normalized post dicts with platform="haufe".
    """
    return _search_site(
        site="haufe.de",
        query=f"Steuerrecht {query}",
        platform="haufe",
        author="Haufe",
        max_results=max_results,
    )


async def crawl_regulatory_updates(query: str = "",
                                    max_results: int = 30) -> list[dict]:
    """Combined regulatory crawler: BMF + BFH + Haufe practitioner commentary.

    Merges results from all three sources, deduplicates by URL, and
    returns a unified list sorted by source priority (BMF > BFH > Haufe).

    Args:
        query: Optional additional search terms to narrow results.
        max_results: Target total results (split across sources).

    Returns:
        Deduplicated list of normalized post dicts from all sources.
    """
    # Split budget across sources — BMF and BFH get priority
    bmf_limit = max(max_results // 3, 5)
    bfh_limit = max(max_results // 3, 5)
    haufe_limit = max(max_results // 4, 5)

    bmf_query = f"BMF Schreiben {query}".strip() if query else "BMF Schreiben aktuell"
    bfh_query = f"BFH Urteil {query}".strip() if query else "BFH Urteil aktuell"
    haufe_query = query if query else "Steuerrecht aktuell"

    # Gather results from all sources
    bmf_results = await crawl_bmf_schreiben(query=bmf_query, max_results=bmf_limit)
    bfh_results = await crawl_bfh_urteile(query=bfh_query, max_results=bfh_limit)
    haufe_results = await crawl_haufe_steuerrecht(query=haufe_query, max_results=haufe_limit)

    # Combine and deduplicate by URL
    combined = bmf_results + bfh_results + haufe_results
    seen_urls: set[str] = set()
    deduplicated: list[dict] = []

    for post in combined:
        url = post.get("url", "")
        # Keep error entries and entries with unique non-empty URLs
        if not url or url not in seen_urls:
            if url:
                seen_urls.add(url)
            deduplicated.append(post)

    return deduplicated[:max_results]
