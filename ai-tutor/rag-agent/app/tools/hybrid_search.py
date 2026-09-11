"""混合检索"""
from typing import List, Tuple, Dict
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Chunk
from .vector_store import search_similar, search_by_keywords


@dataclass
class SearchResult:
    """搜索结果"""
    chunk: Chunk
    score: float
    source: str  # vector, keyword, both


async def hybrid_search(
    db: AsyncSession,
    query: str,
    query_embedding: List[float],
    user_id: UUID,
    top_k: int = 20,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> List[SearchResult]:
    """
    混合检索（向量 + 关键词）
    
    使用 RRF (Reciprocal Rank Fusion) 融合排序
    
    Args:
        db: 数据库会话
        query: 查询文本
        query_embedding: 查询嵌入向量
        user_id: 用户 ID
        top_k: 返回数量
        vector_weight: 向量检索权重
        keyword_weight: 关键词检索权重
    
    Returns:
        搜索结果列表
    """
    # 并行执行两种检索
    vector_results = await search_similar(
        db, query_embedding, user_id, top_k=top_k * 2
    )
    
    # 提取关键词
    keywords = extract_keywords(query)
    keyword_results = await search_by_keywords(
        db, keywords, user_id, top_k=top_k * 2
    )
    
    # RRF 融合排序
    fused_scores: Dict[str, float] = {}
    chunk_map: Dict[str, Chunk] = {}
    
    # 向量检索结果
    for rank, (chunk, score) in enumerate(vector_results):
        chunk_id = str(chunk.id)
        rrf_score = vector_weight / (60 + rank)  # k=60
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0) + rrf_score
        chunk_map[chunk_id] = chunk
    
    # 关键词检索结果
    for rank, (chunk, score) in enumerate(keyword_results):
        chunk_id = str(chunk.id)
        rrf_score = keyword_weight / (60 + rank)  # k=60
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0) + rrf_score
        chunk_map[chunk_id] = chunk
    
    # 排序
    sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
    
    # 构建结果
    results = []
    for chunk_id in sorted_ids[:top_k]:
        chunk = chunk_map[chunk_id]
        score = fused_scores[chunk_id]
        
        # 判断来源
        in_vector = any(str(c.id) == chunk_id for c, _ in vector_results)
        in_keyword = any(str(c.id) == chunk_id for c, _ in keyword_results)
        
        if in_vector and in_keyword:
            source = "both"
        elif in_vector:
            source = "vector"
        else:
            source = "keyword"
        
        results.append(SearchResult(
            chunk=chunk,
            score=score,
            source=source
        ))
    
    return results


def extract_keywords(text: str) -> List[str]:
    """
    提取关键词
    
    简单实现：按空格分词，过滤停用词
    
    Args:
        text: 输入文本
    
    Returns:
        关键词列表
    """
    # 简单停用词
    stop_words = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "他", "她", "它", "那", "些",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "both",
        "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "don't", "now"
    }
    
    # 分词
    words = text.lower().split()
    
    # 过滤停用词和短词
    keywords = [w for w in words if w not in stop_words and len(w) > 1]
    
    return keywords
