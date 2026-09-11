"""网页抓取 - Jina Reader API"""

from dataclasses import dataclass

import httpx

from shared.utils.config import settings


@dataclass
class ScrapeResult:
    """抓取结果"""

    success: bool
    content: str | None = None
    title: str | None = None
    error: str | None = None
    method: str = "jina"


async def scrape_with_jina(url: str, timeout: int = 60) -> ScrapeResult:
    """
    使用 Jina Reader API 抓取网页内容

    Args:
        url: 网页 URL
        timeout: 超时时间（秒）

    Returns:
        ScrapeResult
    """
    if not settings.JINA_API_KEY:
        return ScrapeResult(
            success=False,
            error="Jina API key not configured",
            method="jina",
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Jina Reader API
            api_url = f"https://r.jina.ai/{url}"
            headers = {
                "Authorization": f"Bearer {settings.JINA_API_KEY}",
                "Accept": "text/markdown",
            }

            response = await client.get(api_url, headers=headers)
            response.raise_for_status()

            content = response.text

            # 提取标题（从 Markdown 标题）
            title = None
            if content:
                lines = content.split("\n")
                for line in lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

            return ScrapeResult(
                success=True,
                content=content,
                title=title,
                method="jina",
            )

    except httpx.HTTPStatusError as e:
        return ScrapeResult(
            success=False,
            error=f"HTTP error: {e.response.status_code}",
            method="jina",
        )
    except Exception as e:
        return ScrapeResult(
            success=False,
            error=str(e),
            method="jina",
        )
