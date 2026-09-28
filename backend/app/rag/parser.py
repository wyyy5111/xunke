"""文档解析：PDF / DOCX / PPTX / TXT / MD。"""
from __future__ import annotations
from pathlib import Path
from typing import List
import re
import shutil
import subprocess
import unicodedata

from app.utils.logger import logger


def parse_file(path: str | Path) -> List[dict]:
    """返回 [{"text": ..., "page": int}, ...]。

    二进制格式(pdf/docx/pptx)若解析依赖缺失，返回空列表而非把二进制当文本读
    （否则会污染向量库产生乱码）。
    """
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".")
    try:
        if suffix == "pdf":
            return _clean_pages(_parse_pdf(p))
        if suffix == "docx":
            return _clean_pages(_parse_docx(p))
        if suffix == "pptx":
            return _clean_pages(_parse_pptx(p))
        if suffix in ("txt", "md", "markdown"):
            return _clean_pages(_parse_text(p))
    except Exception as e:
        logger.warning(f"parse {suffix} failed: {e}")
        # 二进制格式绝不退化为纯文本读（会把二进制当文本造成乱码）
        if suffix in ("pdf", "docx", "pptx"):
            logger.error(f"{suffix} 文件解析失败且无对应解析器，跳过该文件避免乱码：{p.name}")
            return []
        # 文本类格式仍可尝试
        return _parse_text(p)
    return []


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\x00", "").replace("\ufffd", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_pages(pages: List[dict]) -> List[dict]:
    cleaned = []
    for page in pages:
        text = _clean_text(str(page.get("text") or ""))
        if len(text) >= 8:
            cleaned.append({"text": text, "page": int(page.get("page") or 1)})
    return cleaned


def _parse_text(p: Path) -> List[dict]:
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        text = p.read_text(encoding="gbk", errors="ignore")
    return [{"text": text, "page": 1}]


def _parse_pdf(p: Path) -> List[dict]:
    out: List[dict] = []
    try:
        from pypdf import PdfReader
    except Exception as e:
        logger.error(f"pypdf 不可用，跳过 PDF 解析以避免二进制乱码：{p.name} ({e})")
        return []
    reader = PdfReader(str(p))
    for i, page in enumerate(reader.pages, 1):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            out.append({"text": t, "page": i})
    extracted_chars = sum(len(item["text"]) for item in out)
    if extracted_chars < 80:
        # Poppler 对部分中文字体映射更稳定；仅传参数列表，不经过 shell。
        try:
            pdftotext = shutil.which("pdftotext")
            if not pdftotext:
                raise FileNotFoundError("pdftotext not installed")
            result = subprocess.run(
                [pdftotext, "-layout", str(p), "-"],
                capture_output=True,
                timeout=45,
                check=False,
            )
            fallback = result.stdout.decode("utf-8", errors="ignore")
            pages = [part for part in fallback.split("\f") if part.strip()]
            if sum(len(part) for part in pages) > extracted_chars:
                out = [{"text": part, "page": idx} for idx, part in enumerate(pages, 1)]
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.debug("pdftotext 兜底不可用，保留原解析结果：%s", exc)
    if not out:
        logger.warning(f"PDF 未提取到可用文本，可能是扫描件：{p.name}")
    return out


def _parse_docx(p: Path) -> List[dict]:
    try:
        import docx
    except Exception as e:
        logger.error(f"python-docx 不可用，跳过 DOCX 解析以避免二进制乱码：{p.name} ({e})")
        return []
    doc = docx.Document(str(p))
    text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    return [{"text": text, "page": 1}] if text.strip() else []


def _parse_pptx(p: Path) -> List[dict]:
    try:
        from pptx import Presentation
    except Exception as e:
        logger.error(f"python-pptx 不可用，跳过 PPTX 解析以避免二进制乱码：{p.name} ({e})")
        return []
    prs = Presentation(str(p))
    out: List[dict] = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs)
                    if line.strip():
                        texts.append(line)
        if texts:
            out.append({"text": "\n".join(texts), "page": i})
    if not out:
        logger.warning(f"PPTX 未提取到可用文本，跳过索引：{p.name}")
    return out
