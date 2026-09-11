"""文档解析"""
from typing import Optional
from dataclasses import dataclass


@dataclass
class ParsedDocument:
    """解析后的文档"""
    title: Optional[str] = None
    content: str = ""
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def parse_document(content: str, title: Optional[str] = None) -> ParsedDocument:
    """
    解析文档内容
    
    支持的格式:
    - Markdown
    - 纯文本
    - HTML (已提取正文)
    
    Args:
        content: 文档内容
        title: 文档标题
    
    Returns:
        ParsedDocument
    """
    # 清理内容
    cleaned_content = content.strip()
    
    # 提取标题（如果未提供）
    if not title:
        lines = cleaned_content.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('# '):
                title = stripped[2:].strip()
                break
            elif stripped and not stripped.startswith('---'):
                # 非空且不是分隔线，可能是标题
                if len(stripped) < 100:
                    title = stripped
                break
    
    return ParsedDocument(
        title=title,
        content=cleaned_content,
        metadata={
            "char_count": len(cleaned_content),
            "line_count": len(cleaned_content.split('\n'))
        }
    )
