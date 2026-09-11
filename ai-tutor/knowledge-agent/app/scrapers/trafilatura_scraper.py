"""网页抓取 - Trafilatura"""

from dataclasses import dataclass

import httpx


@dataclass
class ScrapeResult:
    """抓取结果"""

    success: bool
    content: str | None = None
    title: str | None = None
    error: str | None = None
    method: str = "trafilatura"


async def scrape_with_trafilatura(url: str, timeout: int = 30) -> ScrapeResult:
    """
    使用 trafilatura 抓取网页内容

    Args:
        url: 网页 URL
        timeout: 超时时间（秒）

    Returns:
        ScrapeResult
    """
    try:
        import trafilatura

        # 注意: 必须用 httpx+浏览器 UA 下载。trafilatura.fetch_url 默认 UA 会被
        # 微信公众号等站点反爬拦截，返回"环境异常"验证页，导致正文提取为空。
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            downloaded = response.text

        if not downloaded:
            return ScrapeResult(
                success=False,
                error="Failed to download URL",
                method="trafilatura",
            )

        # 提取正文
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_recall=True,
        )

        # 提取标题
        title = trafilatura.extract(
            downloaded,
            only_with_metadata=False,
            output_format="txt",
            include_comments=False,
        )

        # 如果内容太短，可能提取失败
        if content and len(content) < 100:
            return ScrapeResult(
                success=False,
                content=content,
                error="Extracted content too short",
                method="trafilatura",
            )

        return ScrapeResult(
            success=True,
            content=content,
            title=title.split("\n")[0] if title else None,
            method="trafilatura",
        )

    except Exception as e:
        return ScrapeResult(
            success=False,
            error=str(e),
            method="trafilatura",
        )
