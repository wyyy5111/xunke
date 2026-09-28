"""分块策略：按段落 + 长度滑窗。"""
from __future__ import annotations
from typing import List
import re


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """将长文本切成带 overlap 的块。中文按字符计数。"""
    text = re.sub(r"\s+\n", "\n", text)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: List[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
            step = max(1, chunk_size - overlap)
            for start in range(0, len(para), step):
                piece = para[start:start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
                if start + chunk_size >= len(para):
                    break
            continue
        if len(buf) + len(para) + 1 <= chunk_size:
            buf = (buf + "\n" + para).strip() if buf else para
        else:
            if buf:
                chunks.append(buf)
            # 滑窗 overlap
            if overlap and chunks:
                tail = chunks[-1][-overlap:]
                buf = (tail + " " + para).strip()
            else:
                buf = para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) >= 8]


def chunk_pages(pages: List[dict], chunk_size: int = 500, overlap: int = 80) -> List[dict]:
    """对 [{text, page}] 列表分块，保留 page 信息。"""
    out: List[dict] = []
    for pg in pages:
        for c in chunk_text(pg["text"], chunk_size, overlap):
            out.append({"text": c, "page": pg.get("page", 1)})
    return out
