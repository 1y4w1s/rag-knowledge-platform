"""E4 联网搜索工具 — web_search（SerpAPI）。

需设置 SEARCH_API_KEY 环境变量。
每轮对话限定 ≤3 次（由 run_react_loop 计数门禁管控）。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

SEARCH_API_KEY_ENV = "SEARCH_API_KEY"


@dataclass
class WebSearchResult:
    ok: bool
    data: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""


async def web_search(query: str, num_results: int = 5) -> WebSearchResult:
    """联网搜索，返回 [{title, url, snippet}]。

    Args:
        query: 搜索关键词。
        num_results: 返回结果数（最大 5）。

    Returns:
        WebSearchResult(ok, data, summary)
    """
    api_key = os.environ.get(SEARCH_API_KEY_ENV)
    if not api_key:
        return WebSearchResult(
            ok=False,
            summary=f"web_search 需要 {SEARCH_API_KEY_ENV} 环境变量",
        )

    try:
        import httpx

        params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": min(num_results, 5),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params=params,
            )
            r.raise_for_status()
            data = r.json()

        organic = data.get("organic_results") or []
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in organic[:num_results]
        ]
        logger.info(
            "web_search: query=%.60s results=%d",
            query, len(results),
        )
        return WebSearchResult(
            ok=True,
            data=results,
            summary=f"找到 {len(results)} 条结果",
        )
    except Exception as e:
        logger.warning("web_search 失败: %s", e)
        return WebSearchResult(ok=False, summary=f"web_search 失败: {e}")
