"""文档切分"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    """知识块"""

    content: str
    index: int
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def chunk_document(
    content: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: list[str] | None = None,
) -> list[Chunk]:
    """
    将文档切分为知识块

    Args:
        content: 文档内容
        chunk_size: 块大小（字符数）
        chunk_overlap: 块重叠（字符数）
        separators: 自定义分隔符

    Returns:
        Chunk 列表
    """
    if not content:
        return []

    # 默认分隔符
    if separators is None:
        separators = [
            "\n\n",  # 段落
            "\n",  # 换行
            "。",  # 中文句号
            ".",  # 英文句号
            "！",  # 中文感叹号
            "!",  # 英文感叹号
            "？",  # 中文问号
            "?",  # 英文问号
            "；",  # 中文分号
            ";",  # 英文分号
            "，",  # 中文逗号
            ",",  # 英文逗号
            " ",  # 空格
            "",  # 字符
        ]

    # 创建分割器
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
    )

    # 切分文本
    texts = splitter.split_text(content)

    # 转换为 Chunk 对象
    chunks = []
    for i, text in enumerate(texts):
        if text.strip():  # 跳过空块
            chunks.append(
                Chunk(
                    content=text.strip(),
                    index=i,
                    metadata={
                        "char_count": len(text),
                        "token_estimate": len(text) // 2,  # 粗略估计 token 数
                    },
                ),
            )

    return chunks
