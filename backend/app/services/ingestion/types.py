"""入库管道共享类型（解析 → 切片）。"""

from dataclasses import dataclass
from typing import Literal

BlockKind = Literal["prose", "table"]
ChunkKind = Literal["text", "table", "parent"]


@dataclass
class ParsedBlock:
    """解析器输出的结构单元。"""

    content: str
    page_number: int | None = None
    section_title: str | None = None
    heading_path: str | None = None
    block_kind: BlockKind = "prose"


@dataclass
class ChunkDraft:
    """切片器输出，待嵌入与落库。"""

    content: str
    page_number: int | None = None
    section_title: str | None = None
    heading_path: str | None = None
    chunk_index: int = 0
    chunk_kind: ChunkKind = "text"
    parent_group: str | None = None


@dataclass
class IngestionConfig:
    max_chars: int = 1200
    min_chars: int = 400
    overlap_max_chars: int = 150
    pdf_batch_pages: int = 10
