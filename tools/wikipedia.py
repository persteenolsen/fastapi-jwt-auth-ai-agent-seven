import logging
import traceback
import urllib.parse
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "User-Agent": "FastAPI-Wikipedia-Stable-Agent/1.0",
    "Accept": "application/json"
})


# ------------------------------
# FETCH PAGE SUMMARY
# ------------------------------
def _fetch_page(title: str) -> Optional[Dict[str, Any]]:
    try:
        safe_title = urllib.parse.quote(title.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe_title}"

        r = session.get(url, timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        extract = data.get("extract", "")

        if not extract or len(extract) < 40:
            return None

        return {
            "title": data.get("title", ""),
            "content": extract
        }

    except Exception:
        logger.error(traceback.format_exc())
        return None


# ------------------------------
# SEARCH WIKIPEDIA
# ------------------------------
def _search(query: str) -> List[str]:
    try:
        r = session.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 5,
                "format": "json"
            },
            timeout=10
        )

        r.raise_for_status()

        results = r.json().get("query", {}).get("search", [])
        return [r["title"] for r in results]

    except Exception:
        logger.error(traceback.format_exc())
        return []


# ------------------------------
# SIMPLE SCORING (KEY FIX)
# ------------------------------
def _score(query: str, title: str, text: str) -> int:
    q_words = set(query.lower().split())

    content = (title + " " + text).lower()
    return sum(1 for w in q_words if w in content)


# ------------------------------
# MAIN TOOL
# ------------------------------
def wikipedia_tool(query: str) -> Dict[str, Any]:
    try:
        query = query.strip()

        # 1. direct lookup first (fast path)
        direct = _fetch_page(query)
        if direct:
            return {
                "success": True,
                "source": "wikipedia",
                "title": direct["title"],
                "content": direct["content"]
            }

        # 2. search fallback
        candidates = _search(query)

        if not candidates:
            return {
                "success": False,
                "content": "No Wikipedia result found"
            }

        # 3. rank candidates (IMPORTANT FIX)
        best_result = None
        best_score = -1

        for title in candidates:
            page = _fetch_page(title)
            if not page:
                continue

            score = _score(query, page["title"], page["content"])

            if score > best_score:
                best_score = score
                best_result = page

        if best_result:
            return {
                "success": True,
                "source": "wikipedia",
                "title": best_result["title"],
                "content": best_result["content"]
            }

        return {
            "success": False,
            "content": "No relevant Wikipedia match found"
        }

    except Exception:
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "content": "Wikipedia tool error"
        }