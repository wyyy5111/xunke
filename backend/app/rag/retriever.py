"""持久化本地 RAG 检索与引用溯源。"""
from __future__ import annotations
from typing import List
import re
import numpy as np
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.chunk import DocumentChunk
from app.models.course import CourseFile
from app.models.resource import GeneratedResource
from app.utils.time_util import safe_json_dumps, safe_json_loads


MIN_RELEVANCE_SCORE = 0.02


def _terms(text: str) -> set[str]:
    clean = re.sub(r"\s+", "", text or "")
    words = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,24}|[一-龥]{2,12}", clean))
    words.update(clean[i:i + 2] for i in range(max(0, len(clean) - 1)))
    return {word.lower() for word in words if word.strip()}


def retrieve(db: Session, course_id: int, query: str, top_k: int = 5) -> List[dict]:
    """Use character TF-IDF + lexical overlap against chunks stored in SQLite.

    The database is the source of truth, so retrieval still works after a backend
    restart and does not depend on a process-local index.
    """
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.course_id == course_id)
        .order_by(DocumentChunk.id.asc())
        .all()
    )
    if not chunks or not (query or "").strip():
        return []

    texts = [chunk.text or "" for chunk in chunks]
    try:
        vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            min_df=1,
            sublinear_tf=True,
            norm="l2",
        )
        matrix = vectorizer.fit_transform(texts + [query])
        semantic = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        semantic = np.zeros(len(chunks), dtype=float)

    query_terms = _terms(query)
    scored: list[dict] = []
    for idx, chunk in enumerate(chunks):
        chunk_terms = _terms(chunk.text)
        overlap = len(query_terms & chunk_terms) / max(1, len(query_terms))
        exact_bonus = 0.18 if query.strip() in (chunk.text or "") else 0.0
        score = min(1.0, float(semantic[idx]) * 0.78 + overlap * 0.22 + exact_bonus)
        scored.append({
            "score": round(score, 6),
            "text": chunk.text,
            "page": chunk.page,
            "source": chunk.source_name,
            "chunk_id": chunk.id,
            "file_id": chunk.file_id,
            "chapter": "",
        })
    # Returning zero-similarity chunks creates citations that merely look
    # traceable while providing no evidence for the query. Treat that as a real
    # empty-retrieval state so generators and the UI can disclose the absence of
    # course evidence instead of attaching an arbitrary source.
    relevant = [item for item in scored if item["score"] >= MIN_RELEVANCE_SCORE]
    relevant.sort(key=lambda item: (-item["score"], item["chunk_id"]))
    return relevant[:max(1, min(top_k, 12))]


def format_citations(items: List[dict]) -> List[dict]:
    """规整引用为前端友好结构。"""
    out = []
    for i, it in enumerate(items, 1):
        source_file_id = int(it.get("file_id") or 0)
        source_file_name = it.get("source") or it.get("meta", {}).get("source", "课程资料")
        chapter = str(it.get("chapter") or "未标注章节")
        chunk_id = int(it.get("chunk_id") or 0)
        excerpt = (it.get("text") or "")[:500]
        relevance_score = round(float(it.get("score", 0.0)), 4)
        page_number = int(it.get("page") or it.get("meta", {}).get("page", 1) or 1)
        out.append({
            "id": i,
            "source_file_id": source_file_id,
            "source_file_name": source_file_name,
            "chapter": chapter,
            "chunk_id": chunk_id,
            "excerpt": excerpt,
            "relevance_score": relevance_score,
            "page_number": page_number,
            # Compatibility aliases for existing pages and older resources.
            "score": relevance_score,
            "source": source_file_name,
            "page": page_number,
            "snippet": excerpt[:200],
        })
    return out


def current_course_citations(db: Session, course_id: int, raw: object) -> List[dict]:
    """Return only citations backed by the course's current source files.

    Resource rows intentionally keep a snapshot of generation-time citations.
    A teacher can later delete a source file, and older databases may contain
    malformed or cross-course citation JSON. API responses must never present
    such stale data as currently traceable evidence.
    """
    items = safe_json_loads(raw, []) if isinstance(raw, str) else raw
    if not isinstance(items, list) or not items:
        return []

    file_rows = db.query(CourseFile.id, CourseFile.filename).filter(
        CourseFile.course_id == course_id,
    ).all()
    files = {int(file_id): str(filename or "") for file_id, filename in file_rows}
    names = _file_names(files)

    requested_chunk_ids = {
        value for item in items if isinstance(item, dict)
        if (value := _positive_int(item.get("chunk_id")))
    }
    chunks = {}
    if requested_chunk_ids:
        rows = db.query(DocumentChunk).filter(
            DocumentChunk.course_id == course_id,
            DocumentChunk.id.in_(requested_chunk_ids),
        ).all()
        chunks = {int(row.id): row for row in rows}

    return _validated_items(items, files, names, chunks)


def current_resource_citations(
    db: Session,
    resources: List[GeneratedResource],
) -> dict[int, List[dict]]:
    """Batch variant used by list/dashboard routes to avoid per-row queries."""
    if not resources:
        return {}
    items_by_resource: dict[int, list] = {}
    course_ids = {int(resource.course_id) for resource in resources}
    requested_chunk_ids: set[int] = set()
    for resource in resources:
        items = safe_json_loads(resource.citations, [])
        if not isinstance(items, list):
            items = []
        items_by_resource[int(resource.id)] = items
        requested_chunk_ids.update(
            chunk_id for item in items if isinstance(item, dict)
            if (chunk_id := _positive_int(item.get("chunk_id")))
        )

    files_by_course: dict[int, dict[int, str]] = {course_id: {} for course_id in course_ids}
    file_rows = db.query(CourseFile.id, CourseFile.course_id, CourseFile.filename).filter(
        CourseFile.course_id.in_(course_ids),
    ).all()
    for file_id, course_id, filename in file_rows:
        files_by_course.setdefault(int(course_id), {})[int(file_id)] = str(filename or "")

    chunks_by_course: dict[int, dict[int, DocumentChunk]] = {
        course_id: {} for course_id in course_ids
    }
    if requested_chunk_ids:
        rows = db.query(DocumentChunk).filter(
            DocumentChunk.course_id.in_(course_ids),
            DocumentChunk.id.in_(requested_chunk_ids),
        ).all()
        for row in rows:
            chunks_by_course.setdefault(int(row.course_id), {})[int(row.id)] = row

    result: dict[int, List[dict]] = {}
    for resource in resources:
        course_id = int(resource.course_id)
        files = files_by_course.get(course_id, {})
        result[int(resource.id)] = _validated_items(
            items_by_resource.get(int(resource.id), []),
            files,
            _file_names(files),
            chunks_by_course.get(course_id, {}),
        )
    return result


def _validated_items(
    items: list,
    files: dict[int, str],
    names: dict[str, int],
    chunks: dict[int, DocumentChunk],
) -> List[dict]:
    current: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        citation = dict(item)
        chunk_id = _positive_int(citation.get("chunk_id"))
        file_id = _positive_int(citation.get("source_file_id") or citation.get("file_id"))
        filename = ""

        if chunk_id:
            chunk = chunks.get(chunk_id)
            if not chunk or int(chunk.file_id) not in files:
                continue
            if file_id and file_id != int(chunk.file_id):
                continue
            file_id = int(chunk.file_id)
            filename = files[file_id]
            citation.update({
                "chunk_id": int(chunk.id),
                "source_file_id": file_id,
                "page_number": int(chunk.page or citation.get("page_number") or 1),
                "page": int(chunk.page or citation.get("page") or 1),
            })
        elif file_id:
            filename = files.get(file_id, "")
            if not filename:
                continue
        else:
            legacy_name = _source_basename(
                citation.get("source_file_name") or citation.get("source") or ""
            )
            file_id = names.get(legacy_name, 0)
            if not file_id:
                continue
            filename = files[file_id]

        citation["source_file_id"] = file_id
        citation["source_file_name"] = filename
        citation["source"] = filename
        citation["id"] = len(current) + 1
        current.append(citation)
    return current


def _file_names(files: dict[int, str]) -> dict[str, int]:
    names: dict[str, int] = {}
    for file_id, filename in files.items():
        names.setdefault(_source_basename(filename), file_id)
    return names


def invalidate_deleted_file_citations(
    db: Session,
    *,
    course_id: int,
    file_id: int,
    filename: str,
    chunk_ids: set[int],
) -> list[int]:
    """Detach deleted evidence and return resources requiring re-review."""
    affected: list[int] = []
    source_name = _source_basename(filename)
    resources = db.query(GeneratedResource).filter(
        GeneratedResource.course_id == course_id,
    ).all()
    for resource in resources:
        citations = safe_json_loads(resource.citations, [])
        if not isinstance(citations, list):
            citations = []
        kept: list[dict] = []
        removed = False
        for item in citations:
            if not isinstance(item, dict):
                removed = True
                continue
            citation_file_id = _positive_int(item.get("source_file_id") or item.get("file_id"))
            citation_chunk_id = _positive_int(item.get("chunk_id"))
            legacy_name = _source_basename(
                item.get("source_file_name") or item.get("source") or ""
            )
            belongs_to_deleted_file = (
                citation_file_id == file_id
                or citation_chunk_id in chunk_ids
                or (not citation_file_id and not citation_chunk_id and legacy_name == source_name)
            )
            if belongs_to_deleted_file:
                removed = True
                continue
            kept.append(dict(item))
        if not removed:
            continue
        # Also discard any malformed/cross-course legacy entries while the
        # resource is already being invalidated, so the persisted snapshot is
        # safe as well as the API response.
        kept = current_course_citations(db, course_id, kept)
        resource.citations = safe_json_dumps(kept)
        resource.published = False
        if resource.review_status in {"approved", "published"}:
            resource.review_status = "pending"
        extra = safe_json_loads(resource.extra, {})
        if not isinstance(extra, dict):
            extra = {}
        extra["evidence_status"] = "source_removed_requires_review"
        extra["removed_source_file_id"] = file_id
        resource.extra = safe_json_dumps(extra)
        affected.append(int(resource.id))
    return affected


def _positive_int(value: object) -> int:
    try:
        result = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def _source_basename(value: object) -> str:
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1].strip().casefold()
