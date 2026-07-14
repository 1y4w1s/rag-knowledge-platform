"""对话 API 请求/响应模型（Wave 3.1～3.2 · EW-D4 历史）。"""



from datetime import datetime

from uuid import UUID



from pydantic import BaseModel, Field, model_serializer



from app.models.enums import AgentMode, MessageRole

from app.schemas.citation import CitationSourceStatus





class ChatRequest(BaseModel):

    message: str = Field(..., min_length=1, max_length=8000)
    mode: AgentMode = Field(
        default=AgentMode.fast,
        description="对话模式：fast=快速（现网单次检索）；thorough=精准（Agent 多步只读 tool）；edit=编辑（Agent 只读查库 + 生成 FAQ 草稿）",
    )





class CitationPayload(BaseModel):

    chunk_id: UUID

    document_id: UUID

    doc_name: str

    page: int | None = None

    section_title: str | None = None

    excerpt: str

    kb_id: UUID | None = None

    kb_name: str | None = None





class HistoryCitationPayload(CitationPayload):

    """历史消息引用；不可见库时附带 source_status（ORG-1.7）。"""



    source_status: CitationSourceStatus | None = None



    @model_serializer(mode="wrap")

    def serialize_model(self, handler):

        data = handler(self)

        if data.get("source_status") is None:

            data.pop("source_status", None)

        if data.get("kb_id") is None:

            data.pop("kb_id", None)

        if data.get("kb_name") is None:

            data.pop("kb_name", None)

        return data





class ChatDonePayload(BaseModel):
    message_id: UUID
    citations: list[CitationPayload]
    agent_run_id: UUID | None = None
    approval_id: UUID | None = None
    approval_status: str | None = None





class ChatMessageResponse(BaseModel):
    id: UUID
    role: MessageRole
    content: str
    citations: list[HistoryCitationPayload] | None = None
    approval_id: UUID | None = None
    approval_status: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}





class ChatMessagesListResponse(BaseModel):

    messages: list[ChatMessageResponse] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    """对话历史搜索结果条目。"""
    thread_id: UUID
    thread_title: str
    thread_kind: str
    kb_id: UUID | None = None
    kb_name: str | None = None
    message_id: UUID
    role: MessageRole
    content: str
    created_at: datetime


class SearchMessagesResponse(BaseModel):
    items: list[SearchResultItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int

