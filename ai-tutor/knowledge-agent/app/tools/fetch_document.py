"""文档抓取工具"""
from typing import Optional, Literal
from dataclasses import dataclass

from ..scrapers import scrape_with_trafilatura, scrape_with_jina


@dataclass
class FetchResult:
    """抓取结果"""
    success: bool
    content: Optional[str] = None
    title: Optional[str] = None
    error: Optional[str] = None
    method: str = "trafilatura"
    needs_fallback: bool = False


async def fetch_document(
    url: str,
    method: Literal["auto", "trafilatura", "jina"] = "auto"
) -> FetchResult:
    """
    抓取文档
    
    Args:
        url: 文档 URL
        method: 抓取方法
            - auto: 自动选择，trafilatura 失败时尝试 jina
            - trafilatura: 仅使用 trafilatura
            - jina: 仅使用 jina
    
    Returns:
        FetchResult
    """
    if method == "trafilatura" or method == "auto":
        result = await scrape_with_trafilatura(url)
        
        if result.success:
            return FetchResult(
                success=True,
                content=result.content,
                title=result.title,
                method="trafilatura"
            )
        
        # auto 模式下，trafilatura 失败时尝试 jina
        if method == "auto":
            jina_result = await scrape_with_jina(url)
            
            if jina_result.success:
                return FetchResult(
                    success=True,
                    content=jina_result.content,
                    title=jina_result.title,
                    method="jina"
                )
            
            # 都失败了，返回需要人工决策
            return FetchResult(
                success=False,
                error=f"trafilatura: {result.error}, jina: {jina_result.error}",
                needs_fallback=True
            )
        
        # 指定 trafilatura 但失败
        return FetchResult(
            success=False,
            error=result.error,
            method="trafilatura",
            needs_fallback=True
        )
    
    elif method == "jina":
        result = await scrape_with_jina(url)
        
        return FetchResult(
            success=result.success,
            content=result.content,
            title=result.title,
            error=result.error,
            method="jina"
        )
    
    else:
        return FetchResult(
            success=False,
            error=f"Unknown method: {method}"
        )
