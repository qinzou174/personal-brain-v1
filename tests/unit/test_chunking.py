"""Unit tests: paragraph-boundary chunking for long-document semantic indexing."""
from __future__ import annotations

from personal_brain_infra.search.chunking import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHUNK_THRESHOLD,
    split_chunks,
)


def _paragraph(tag: str, lines: int, line_length: int = 40) -> str:
    return "\n".join(f"{tag}-{index:03d}-{'x' * line_length}" for index in range(lines))


def test_short_text_is_returned_unchanged_as_single_chunk():
    text = "一句话笔记"
    assert split_chunks(text) == [text]
    assert split_chunks("x" * (CHUNK_THRESHOLD - 1)) == ["x" * (CHUNK_THRESHOLD - 1)]


def test_threshold_boundary_chunks_at_or_above_threshold():
    exactly = split_chunks("x" * CHUNK_THRESHOLD)
    assert len(exactly) >= 2


def test_empty_and_whitespace_only_text_yield_no_chunks():
    assert split_chunks("") == []
    assert split_chunks("   \n\n  ") == []


def test_paragraphs_packed_toward_chunk_size():
    text = "\n\n".join(_paragraph(f"段{index}", 3) for index in range(40))
    blocks = split_chunks(text)
    assert len(blocks) >= 2
    for block in blocks:
        # A block may exceed the soft target only by the carried overlap tail.
        assert len(block) <= CHUNK_SIZE + CHUNK_OVERLAP + len(_paragraph("段0", 1))


def test_adjacent_blocks_share_the_overlap_tail():
    text = "\n\n".join(_paragraph(f"段{index}", 4) for index in range(30))
    blocks = split_chunks(text)
    assert len(blocks) >= 3
    for previous, following in zip(blocks, blocks[1:]):
        tail = previous[-CHUNK_OVERLAP:]
        assert following.startswith(tail), "the boundary tail must repeat across chunks"


def test_long_single_paragraph_is_hard_cut():
    text = "无换行长文。" * 500  # 3000 chars, no newlines at all
    blocks = split_chunks(text)
    assert len(blocks) >= 2
    for block in blocks:
        assert len(block) <= CHUNK_SIZE + CHUNK_OVERLAP + 2


def test_every_paragraph_survives_in_some_block():
    paragraphs = [_paragraph(f"段{index}", 2) for index in range(30)]
    blocks = split_chunks("\n\n".join(paragraphs))
    for paragraph in paragraphs:
        head = paragraph.split("\n")[0]
        assert any(head in block for block in blocks), f"lost paragraph head: {head}"


def test_chunking_is_deterministic():
    text = "\n\n".join(_paragraph(f"段{index}", 3) for index in range(20))
    assert split_chunks(text) == split_chunks(text)
