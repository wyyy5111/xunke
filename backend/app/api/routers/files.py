"""课程资料上传 / 解析。"""
from __future__ import annotations
import io
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import teacher_or_admin, any_role
from app.models.chunk import DocumentChunk
from app.models.course import Course, CourseEnrollment, CourseFile
from app.models.user import User
from app.schemas.common import R
from app.schemas.course import FileOut
from app.agents.orchestrator import run_parse_only
from app.rag.retriever import invalidate_deleted_file_citations
from app.utils.logger import logger

router = APIRouter(prefix="/api/files", tags=["file"])

ALLOWED = {"pdf", "docx", "pptx", "txt", "md", "markdown"}
MIME_ALLOWLIST = {
    "pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip", "application/x-zip-compressed", "application/octet-stream",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip", "application/x-zip-compressed", "application/octet-stream",
    },
    "txt": {"text/plain", "application/octet-stream"},
    "md": {"text/plain", "text/markdown", "text/x-markdown", "application/octet-stream"},
    "markdown": {"text/plain", "text/markdown", "text/x-markdown", "application/octet-stream"},
}


@router.post("/upload/{course_id}", response_model=R)
async def upload_file(course_id: int, bg: BackgroundTasks,
                      file: UploadFile = File(...),
                      db: Session = Depends(get_db),
                      user: User = Depends(teacher_or_admin)):
    _managed_course(db, course_id, user)
    original_name = Path((file.filename or "").replace("\\", "/")).name.strip()
    original_name = re.sub(r"[\x00-\x1f\x7f]", "", original_name)[:240]
    if not original_name or "." not in original_name:
        raise HTTPException(400, "文件名或扩展名无效")
    suffix = original_name.rsplit(".", 1)[-1].lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"不支持的文件类型: {suffix}")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    await file.close()
    if not content:
        raise HTTPException(400, "不能上传空文件")
    if len(content) > max_bytes:
        raise HTTPException(400, f"文件过大，限制 {settings.MAX_UPLOAD_MB}MB")
    _validate_upload_content(suffix, content, file.content_type or "")

    # 文件名由服务端生成；原始名称仅用于页面显示。
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    save_dir = (upload_root / f"course_{course_id}").resolve()
    if save_dir != upload_root and upload_root not in save_dir.parents:
        raise HTTPException(400, "文件存储路径无效")
    save_dir.mkdir(parents=True, exist_ok=True)
    target = (save_dir / f"{uuid.uuid4().hex}.{suffix}").resolve()
    if save_dir not in target.parents:
        raise HTTPException(400, "文件存储路径无效")
    target.write_bytes(content)

    cf = CourseFile(course_id=course_id, uploader_id=user.id, filename=original_name,
                    stored_path=str(target), file_type=suffix, size=len(content),
                    parse_status="pending")
    try:
        db.add(cf)
        db.commit()
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    db.refresh(cf)

    # 后台触发解析
    bg.add_task(_parse_task, cf.id, course_id)
    return R.ok(FileOut.model_validate(cf).model_dump(mode="json"))


def _parse_task(file_id: int, course_id: int):
    db = SessionLocal()
    try:
        run = run_parse_only(db, course_id, file_id)
        course_file = db.get(CourseFile, file_id)
        chunks = db.query(DocumentChunk).filter(DocumentChunk.file_id == file_id).count()
        if course_file and (run.status != "success" or chunks == 0):
            course_file.parse_status = "failed"
            course_file.indexed = False
            course_file.parse_summary = run.error or "未从文件中提取到可用文本，请检查文件是否为扫描件或损坏文件"
            db.commit()
            logger.warning("file %s parse failed: %s", file_id, course_file.parse_summary)
        else:
            logger.info("file %s parsed done", file_id)
    except Exception as e:
        db.rollback()
        course_file = db.get(CourseFile, file_id)
        if course_file:
            course_file.parse_status = "failed"
            course_file.indexed = False
            course_file.parse_summary = f"解析任务异常：{type(e).__name__}"
            db.commit()
        logger.exception(f"parse task failed: {e}")
    finally:
        db.close()


@router.get("/course/{course_id}", response_model=R)
def list_files(course_id: int, db: Session = Depends(get_db),
               user: User = Depends(any_role)):
    _accessible_course(db, course_id, user)
    rows = db.query(CourseFile).filter(CourseFile.course_id == course_id).order_by(
        CourseFile.id.desc()).all()
    return R.ok([FileOut.model_validate(f).model_dump(mode="json") for f in rows])


@router.delete("/{file_id}", response_model=R)
def delete_file(file_id: int, db: Session = Depends(get_db),
                user: User = Depends(teacher_or_admin)):
    f = db.get(CourseFile, file_id)
    if not f:
        raise HTTPException(404, "文件不存在")
    _managed_course(db, f.course_id, user)
    chunk_ids = {
        int(chunk_id) for (chunk_id,) in db.query(DocumentChunk.id).filter(
            DocumentChunk.file_id == file_id,
        ).all()
    }
    try:
        affected_resources = invalidate_deleted_file_citations(
            db,
            course_id=f.course_id,
            file_id=f.id,
            filename=f.filename,
            chunk_ids=chunk_ids,
        )
        db.query(DocumentChunk).filter(DocumentChunk.file_id == file_id).delete(
            synchronize_session=False
        )
        db.delete(f)
        db.flush()
        _resolve_stored_path(f.stored_path).unlink(missing_ok=True)
    except OSError as exc:
        db.rollback()
        raise HTTPException(500, "删除文件失败，请检查文件存储权限") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "文件仍被其他业务数据引用，暂时无法删除") from exc
    db.commit()
    return R.ok({
        "id": file_id,
        "invalidated_resource_ids": affected_resources,
        "invalidated_resource_count": len(affected_resources),
    })


@router.post("/{file_id}/retry", response_model=R)
def retry_parse(file_id: int, bg: BackgroundTasks,
                db: Session = Depends(get_db),
                user: User = Depends(teacher_or_admin)):
    """Retry parsing an existing upload without asking the teacher to re-upload it."""
    course_file = db.get(CourseFile, file_id)
    if not course_file:
        raise HTTPException(404, "文件不存在")
    _managed_course(db, course_file.course_id, user)
    path = _resolve_stored_path(course_file.stored_path)
    if not path.is_file():
        raise HTTPException(404, "原始文件已丢失，请重新上传")
    if course_file.parse_status in {"pending", "parsing", "indexing"}:
        raise HTTPException(409, "文件正在处理中，请稍后刷新状态")
    course_file.parse_status = "pending"
    course_file.parse_summary = "已重新提交解析任务"
    course_file.indexed = False
    db.commit()
    bg.add_task(_parse_task, course_file.id, course_file.course_id)
    return R.ok({
        "id": course_file.id,
        "status": course_file.parse_status,
        "summary": course_file.parse_summary,
        "indexed": course_file.indexed,
    })


@router.get("/{file_id}/parse_status", response_model=R)
def parse_status(file_id: int, db: Session = Depends(get_db),
                 user: User = Depends(any_role)):
    f = db.get(CourseFile, file_id)
    if not f:
        raise HTTPException(404, "文件不存在")
    _accessible_course(db, f.course_id, user)
    return R.ok({"status": f.parse_status, "summary": f.parse_summary, "indexed": f.indexed})


@router.get("/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db),
                  user: User = Depends(any_role)):
    file_row = db.get(CourseFile, file_id)
    if not file_row:
        raise HTTPException(404, "文件不存在")
    _accessible_course(db, file_row.course_id, user)
    path = _resolve_stored_path(file_row.stored_path)
    if not path.is_file():
        raise HTTPException(404, "原始文件已丢失")
    return FileResponse(path, filename=file_row.filename, media_type="application/octet-stream")


def _validate_upload_content(suffix: str, content: bytes, content_type: str) -> None:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type and media_type not in MIME_ALLOWLIST[suffix]:
        raise HTTPException(400, "文件内容类型与扩展名不匹配")
    if suffix == "pdf":
        if b"%PDF-" not in content[:1024]:
            raise HTTPException(400, "PDF 文件头无效或文件已损坏")
        return
    if suffix in {"docx", "pptx"}:
        _validate_ooxml(suffix, content)
        return
    if b"\x00" in content:
        raise HTTPException(400, "文本文件包含二进制内容")
    decoded = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            decoded = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise HTTPException(400, "文本文件编码不受支持，请使用 UTF-8 或 GB18030")
    sample = decoded[:10000]
    controls = sum(1 for char in sample if ord(char) < 32 and char not in "\n\r\t")
    if sample and controls / len(sample) > 0.01:
        raise HTTPException(400, "文本文件包含异常控制字符")


def _validate_ooxml(suffix: str, content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > 5000:
                raise HTTPException(400, "Office 文件结构异常")
            total_uncompressed = 0
            names = set()
            max_total_uncompressed = min(
                settings.MAX_UPLOAD_MB * 1024 * 1024 * 3,
                150 * 1024 * 1024,
            )
            max_single_entry = min(
                settings.MAX_UPLOAD_MB * 1024 * 1024,
                64 * 1024 * 1024,
            )
            for info in infos:
                path = PurePosixPath(info.filename)
                if info.filename.startswith("/") or ".." in path.parts or info.flag_bits & 0x1:
                    raise HTTPException(400, "Office 文件包含不安全条目")
                if info.filename in names:
                    raise HTTPException(400, "Office 文件包含重复条目")
                if info.file_size > max_single_entry:
                    raise HTTPException(400, "Office 文件单个条目解压体积异常")
                if (
                    info.file_size > 10 * 1024 * 1024
                    and info.compress_size > 0
                    and info.file_size / info.compress_size > 100
                ):
                    raise HTTPException(400, "Office 文件压缩比异常")
                total_uncompressed += max(0, info.file_size)
                names.add(info.filename)
            if total_uncompressed > max_total_uncompressed:
                raise HTTPException(400, "Office 文件解压体积异常")
            required_prefix = "word/" if suffix == "docx" else "ppt/"
            if "[Content_Types].xml" not in names or not any(name.startswith(required_prefix) for name in names):
                raise HTTPException(400, "Office 文件类型与扩展名不匹配")
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Office 文件头无效或文件已损坏") from exc


def _resolve_stored_path(raw_path: str) -> Path:
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    path = Path(raw_path).resolve()
    if path != upload_root and upload_root not in path.parents:
        raise HTTPException(400, "文件存储路径无效")
    return path


def _managed_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "无权管理其他教师的课程资料")
    return course


def _accessible_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "admin":
        return course
    if user.role == "teacher":
        if course.teacher_id != user.id:
            raise HTTPException(403, "无权访问其他教师的课程资料")
        return course
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == user.id,
    ).first()
    if not enrolled:
        raise HTTPException(403, "请先加入该课程")
    return course
