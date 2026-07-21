"""结构优先切片（TECH-4.3.2）+ 表格独立 chunk / Parent-Child（R2-2）。"""



from __future__ import annotations



import re



from app.services.ingestion.types import ChunkDraft, IngestionConfig, ParsedBlock



SENTENCE_END = re.compile(r"[。！？!?；;……]|(?:——)+|(?<=\.) (?=[A-Z0-9])|(?<=:)(?= )")
SOFT_MAX_MARGIN = 0.2





def _section_key(block: ParsedBlock) -> str:

    return block.heading_path or block.section_title or "__body__"





def _last_sentence(text: str, max_chars: int) -> str:

    sentences = re.split(SENTENCE_END, text.strip())

    sentences = [s for s in sentences if s.strip()]

    if not sentences:

        return text[-max_chars:] if len(text) > max_chars else text



    tail = ""

    for sentence in reversed(sentences):

        candidate = sentence + tail

        if len(candidate) > max_chars:

            break

        tail = candidate

    return tail or sentences[-1][-max_chars:]





def _split_long_text(

    text: str,

    *,

    meta: ParsedBlock,

    max_chars: int,

) -> list[ParsedBlock]:

    if len(text) <= max_chars:

        return [

            ParsedBlock(

                content=text,

                page_number=meta.page_number,

                section_title=meta.section_title,

                heading_path=meta.heading_path,

                block_kind=meta.block_kind,

            )

        ]



    soft_max = int(max_chars * (1 + SOFT_MAX_MARGIN))
    sentences = re.split(SENTENCE_END, text.strip())

    sentences = [s for s in sentences if s.strip()]

    parts: list[ParsedBlock] = []

    current = ""



    for sentence in sentences:

        if len(current) + len(sentence) <= soft_max:

            current += sentence

            continue

        if current:

            parts.append(

                ParsedBlock(

                    content=current.strip(),

                    page_number=meta.page_number,

                    section_title=meta.section_title,

                    heading_path=meta.heading_path,

                    block_kind=meta.block_kind,

                )

            )

        current = sentence



    if current.strip():

        parts.append(

            ParsedBlock(

                content=current.strip(),

                page_number=meta.page_number,

                section_title=meta.section_title,

                heading_path=meta.heading_path,

                block_kind=meta.block_kind,

            )

        )

    return parts





def _leaf_chunks_for_prose(

    blocks: list[ParsedBlock],

    cfg: IngestionConfig,

) -> list[ChunkDraft]:

    """对同节 prose 块执行 P0 切片（不含 parent 行）。"""

    expanded: list[ParsedBlock] = []



    for block in blocks:

        text = block.content.strip()

        if not text:

            continue

        if len(text) > cfg.max_chars:

            expanded.extend(

                _split_long_text(text, meta=block, max_chars=cfg.max_chars)

            )

        else:

            expanded.append(block)



    merged: list[ParsedBlock] = []

    for block in expanded:

        if merged and len(merged[-1].content) < cfg.min_chars:

            prev = merged[-1]

            same_section = (

                prev.heading_path == block.heading_path

                and prev.section_title == block.section_title

            )

            combined = f"{prev.content}\n{block.content}".strip()

            if same_section and len(combined) <= cfg.max_chars:

                # 放宽句子边界：小 chunk 优先合并
                last_sent = _last_sentence(prev.content, cfg.overlap_max_chars)
                page_transition = (prev.page_number is not None and block.page_number is not None
                                   and block.page_number == prev.page_number + 1)
                if last_sent and len(last_sent) < 4 and len(merged[-1].content) > cfg.min_chars and not page_transition:
                    merged.append(block)
                    continue

                merged[-1] = ParsedBlock(

                    content=combined,

                    page_number=block.page_number or prev.page_number,

                    section_title=block.section_title or prev.section_title,

                    heading_path=block.heading_path or prev.heading_path,

                    block_kind="prose",

                )

                continue

        merged.append(block)



    chunks: list[ChunkDraft] = []

    prev_tail = ""



    for block in merged:

        content = block.content.strip()

        if prev_tail and not content.startswith(prev_tail):

            content = f"{prev_tail}{content}"



        chunks.append(

            ChunkDraft(

                content=content,

                page_number=block.page_number,

                section_title=block.section_title,

                heading_path=block.heading_path,

                chunk_kind="text",

            )

        )

        prev_tail = _last_sentence(content, cfg.overlap_max_chars)



    return chunks





def _chunk_prose_section(

    blocks: list[ParsedBlock],

    cfg: IngestionConfig,

) -> list[ChunkDraft]:

    children = _leaf_chunks_for_prose(blocks, cfg)

    if len(children) <= 1:

        return children



    group = _section_key(blocks[0])

    parent_text = "\n\n".join(b.content.strip() for b in blocks if b.content.strip())

    parent = ChunkDraft(

        content=parent_text,

        page_number=blocks[0].page_number,

        section_title=blocks[0].section_title,

        heading_path=blocks[0].heading_path,

        chunk_kind="parent",

        parent_group=group,

    )

    for child in children:

        child.parent_group = group

    return [parent, *children]





def structure_chunk(

    blocks: list[ParsedBlock],

    config: IngestionConfig | None = None,

) -> list[ChunkDraft]:

    cfg = config or IngestionConfig()

    result: list[ChunkDraft] = []

    prose_buffer: list[ParsedBlock] = []

    current_section: str | None = None



    def flush_prose() -> None:

        nonlocal prose_buffer, current_section

        if not prose_buffer:

            return

        result.extend(_chunk_prose_section(prose_buffer, cfg))

        prose_buffer = []

        current_section = None



    for block in blocks:

        text = block.content.strip()

        if not text:

            continue



        if block.block_kind == "table":

            flush_prose()

            from app.services.ingestion.table_split import split_table_block

            result.extend(
                split_table_block(
                    ParsedBlock(
                        content=text,
                        page_number=block.page_number,
                        section_title=block.section_title,
                        heading_path=block.heading_path,
                        block_kind="table",
                    ),
                    max_chars=cfg.max_chars,
                    row_overlap=cfg.table_row_overlap,
                    parent_max_chars=cfg.table_parent_max_chars,
                    enabled=cfg.table_chunk_split_enabled,
                )
            )

            continue



        section = _section_key(block)

        if prose_buffer and section != current_section:

            flush_prose()

        current_section = section

        prose_buffer.append(block)



    flush_prose()



    for idx, chunk in enumerate(result):

        chunk.chunk_index = idx



    return result


