"""向量化工具"""

from dataclasses import dataclass

from shared.llm import llm_router


@dataclass
class EmbeddingResult:
    """嵌入结果"""

    success: bool
    embeddings: list[list[float]] = None
    error: str | None = None

    def __post_init__(self):
        if self.embeddings is None:
            self.embeddings = []


async def embed_chunks(texts: list[str]) -> EmbeddingResult:
    """
    为文本块生成嵌入向量

    Args:
        texts: 文本列表

    Returns:
        EmbeddingResult
    """
    if not texts:
        return EmbeddingResult(success=True, embeddings=[])

    try:
        embeddings = await llm_router.embed(texts)

        return EmbeddingResult(
            success=True,
            embeddings=embeddings,
        )

    except Exception as e:
        return EmbeddingResult(
            success=False,
            error=str(e),
        )


async def embed_single(text: str) -> list[float] | None:
    """
    为单个文本生成嵌入向量

    Args:
        text: 文本

    Returns:
        嵌入向量，失败返回 None
    """
    result = await embed_chunks([text])

    if result.success and result.embeddings:
        return result.embeddings[0]

    return None
