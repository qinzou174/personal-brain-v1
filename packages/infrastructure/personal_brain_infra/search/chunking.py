"""Paragraph-boundary chunking for long-document semantic indexing.

A whole-document embedding averages every topic in the text, so a query about
one specific section of a long document finds the card weak (the semantic-list
blind spot behind the RRF single-list drowning, 2026-09-26). Splitting the
document into focused ~600-character slices gives each section its own vector;
retrieval takes the parent card's best chunk.

Chunking operates on the *raw* text, before ``fts_text()`` token deduplication
(length-normalization lesson #14), and is purely a function of the text so it
is trivially unit-testable and deterministic across re-index runs.
"""

from __future__ import annotations

CHUNK_THRESHOLD = 2000   # characters; >= this length is chunked
CHUNK_SIZE = 600         # soft target length per chunk
CHUNK_OVERLAP = 100      # characters carried from the previous chunk

# Sentence punctuation preferred for hard cuts inside an oversized paragraph.
_SEPARATORS = ("。", "！", "？", ".", "!", "?", "；", ";", "，", ",")


def _hard_cut(paragraph: str) -> int:
    """One cut point in (CHUNK_SIZE//2, CHUNK_SIZE], snapping to a newline,
    then sentence punctuation; falls back to a hard character cut."""
    window = paragraph[:CHUNK_SIZE]
    cut = window.rfind("\n")
    if cut >= CHUNK_SIZE // 2:
        return cut + 1
    for separator in _SEPARATORS:
        cut = window.rfind(separator)
        if cut >= CHUNK_SIZE // 2:
            return cut + len(separator)
    return CHUNK_SIZE


def _atomic_units(text: str) -> list[str]:
    """Paragraphs, with oversized paragraphs cut into <=CHUNK_SIZE pieces."""
    units: list[str] = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while len(paragraph) > CHUNK_SIZE:
            cut = _hard_cut(paragraph)
            units.append(paragraph[:cut].strip())
            paragraph = paragraph[max(0, cut - CHUNK_OVERLAP):].strip()
        if paragraph:
            units.append(paragraph)
    return units


def split_chunks(text: str) -> list[str]:
    """Split ``text`` into ordered semantic chunks.

    Texts shorter than ``CHUNK_THRESHOLD`` come back as a single chunk (the
    no-chunking path); otherwise paragraphs are packed toward ``CHUNK_SIZE``
    with a ``CHUNK_OVERLAP`` character tail repeated across the boundary.
    Whitespace-only input yields an empty list.
    """
    if not text or not text.strip():
        return []
    if len(text) < CHUNK_THRESHOLD:
        return [text]
    blocks: list[str] = []
    current = ""
    for unit in _atomic_units(text):
        candidate = f"{current}\n{unit}" if current else unit
        if current and len(candidate) > CHUNK_SIZE:
            blocks.append(current)
            current = f"{current[-CHUNK_OVERLAP:]}\n{unit}"
        else:
            current = candidate
    if current:
        blocks.append(current)
    return blocks
