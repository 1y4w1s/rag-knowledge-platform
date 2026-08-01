"""D1 GraphRAG — 实体/关系抽取助手（同步版 DeepSeek JSON mode）。

用于 ingestion 线程（asyncio.to_thread 内，无事件循环）。
熔断由 get_breaker("deepseek_llm").record_success/failure 手工标记。
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.retry import get_breaker
from app.models.entity import Entity, EntityMention, Relation
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.observability.metrics_registry import inc_llm_failure, inc_llm_success

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2

_EXTRACTION_PROMPT = """你是一名实体关系抽取助手。从以下文本中抽取实体和关系。

支持的实体类型：person, organization, project, contract_number, amount, date, product
支持的关系类型：belongs_to, responsible_for, participates_in, contract_with, parent_of

输出严格 JSON 格式（不要 markdown 代码块）：
{{
  "entities": [{{"name": "...", "type": "..."}}],
  "relations": [{{"source": "...", "target": "...", "type": "..."}}]
}}

文本内容：
{text}"""


def _try_parse_json(raw: str) -> dict:
    """尝试解析 JSON 响应，含兜底策略。

    1. 直接 json.loads
    2. 截取第一个 {...} 再解析
    3. 兜底返回空结构
    """
    # 尝试 1：直接解析
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试 2：截取第一个 { 到最后一个 }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    # 兜底
    logger.warning("extract_entities_sync: 畸形 JSON 响应，返回空结构. raw=%.200s", raw)
    return {"entities": [], "relations": []}


def extract_entities_sync(
    text: str,
    supported_types: list[str] | None = None,
) -> dict:
    """同步调用 DeepSeek JSON mode，返回 {entities: [...], relations: [...]}。

    独立非流式助手，不经过 chat_llm.py 的 stream 路径。
    纯同步函数（内部用 httpx.Client），必须通过
    await asyncio.to_thread(extract_entities_sync, chunk.content)
    调用，不可在事件循环内直接调。
    """
    api_key = settings.deepseek_api_key
    if not api_key:
        logger.warning("extract_entities_sync: DEEPSEEK_API_KEY 未配置")
        return {"entities": [], "relations": []}

    base_url = (settings.deepseek_base_url or "").rstrip("/")
    url = f"{base_url}/chat/completions"
    model = settings.deepseek_model or "deepseek-chat"

    prompt = _EXTRACTION_PROMPT.format(text=text)
    messages = [
        {"role": "system", "content": prompt},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    breaker = get_breaker("deepseek_llm")
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"] or ""
                breaker.record_success()
                inc_llm_success()
                parsed = _try_parse_json(raw)
                entities = parsed.get("entities", [])
                relations = parsed.get("relations", [])
                return {"entities": entities, "relations": relations}
        except Exception as e:
            breaker.record_failure()
            inc_llm_failure()
            logger.warning(
                "extract_entities_sync 尝试 %d/%d 失败: %s",
                attempt + 1, _MAX_RETRIES, e,
            )
            if attempt == _MAX_RETRIES - 1:
                return {"entities": [], "relations": []}
    return {"entities": [], "relations": []}


async def extract_entities_for_document(db: AsyncSession, doc: Document) -> None:
    """文档入库后抽取实体与关系。

    时机：_write_chunks 之后、db.commit 之前（同一事务内）。
    输入：从 DB 读取该 document 的所有 chunk。
    输出：写入 entities / entity_mentions / relations 表。
    """
    if not settings.deepseek_api_key:
        logger.info("extract_entities_for_document: DEEPSEEK_API_KEY 未配置，跳过")
        return

    # 1. 读取文档的所有 chunk
    result = await db.execute(
        select(DocumentChunk).where(
            DocumentChunk.document_id == doc.id,
            DocumentChunk.chunk_kind != "parent",
        )
    )
    chunks = result.scalars().all()
    if not chunks:
        return

    # 2. 对每 chunk 抽取实体
    all_entities: list[dict] = []
    all_relations: list[dict] = []
    chunk_entity_map: dict[UUID, list[str]] = {}

    for chunk in chunks:
        extracted = await asyncio.to_thread(extract_entities_sync, chunk.content)
        chunk_entities = extracted.get("entities", [])
        chunk_relations = extracted.get("relations", [])

        if chunk_entities:
            all_entities.extend(chunk_entities)
            chunk_entity_map[chunk.id] = [e["name"] for e in chunk_entities]
        if chunk_relations:
            all_relations.extend(chunk_relations)

    if not all_entities and not all_relations:
        return

    # 3. exact-match upsert 实体
    unique_entities: dict[tuple[str, str], UUID] = {}
    entity_name_to_id: dict[str, UUID] = {}

    for ent in all_entities:
        key = (ent["name"], ent["type"])
        if key in unique_entities:
            continue
        existing = await db.execute(
            select(Entity).where(
                Entity.kb_id == doc.kb_id,
                Entity.name == ent["name"],
                Entity.type == ent["type"],
            )
        )
        existing_entity = existing.scalar_one_or_none()
        if existing_entity is not None:
            unique_entities[key] = existing_entity.id
            entity_name_to_id[ent["name"]] = existing_entity.id
        else:
            new_entity = Entity(
                kb_id=doc.kb_id,
                name=ent["name"],
                type=ent["type"],
            )
            db.add(new_entity)
            await db.flush()
            unique_entities[key] = new_entity.id
            entity_name_to_id[ent["name"]] = new_entity.id

    # 4. 写 entity_mentions
    for chunk_id, entity_names in chunk_entity_map.items():
        for ent_name in entity_names:
            eid = entity_name_to_id.get(ent_name)
            if eid is None:
                continue
            exists = await db.execute(
                select(EntityMention).where(
                    EntityMention.chunk_id == chunk_id,
                    EntityMention.entity_id == eid,
                )
            )
            if exists.scalar_one_or_none() is None:
                mention = EntityMention(
                    chunk_id=chunk_id,
                    entity_id=eid,
                )
                db.add(mention)

    # 5. 写 relations
    for rel in all_relations:
        source_id = entity_name_to_id.get(rel["source"])
        target_id = entity_name_to_id.get(rel["target"])
        if source_id is None or target_id is None:
            logger.warning(
                "extract_entities_for_document: relation 引用未知实体 source=%s target=%s",
                rel.get("source"), rel.get("target"),
            )
            continue
        exists = await db.execute(
            select(Relation).where(
                Relation.kb_id == doc.kb_id,
                Relation.source_id == source_id,
                Relation.target_id == target_id,
                Relation.relation_type == rel["type"],
            )
        )
        if exists.scalar_one_or_none() is None:
            relation = Relation(
                kb_id=doc.kb_id,
                source_id=source_id,
                target_id=target_id,
                relation_type=rel["type"],
            )
            db.add(relation)

    await db.flush()
    logger.info(
        "extract_entities_for_document: doc=%s entities=%d mentions=%d relations=%d",
        doc.id,
        len(unique_entities),
        sum(len(v) for v in chunk_entity_map.values()),
        len(all_relations),
    )
