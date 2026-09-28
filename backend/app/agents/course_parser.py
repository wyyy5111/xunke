"""1. CourseParserAgent：解析课程文件 -> 章节/知识点/持久化检索片段。"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models.course import CourseFile, CourseChapter
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.chunk import DocumentChunk
from app.rag.parser import parse_file
from app.rag.chunker import chunk_pages
from app.services.llm_client import llm_client
from app.agents.prompts import course_parse_prompt


class CourseParserAgent(BaseAgent):
    name = "CourseParserAgent"
    purpose = "course_parse"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary.get("course_id")
        file_id = input_summary.get("file_id")
        course = self.db.get(Course, course_id)
        if not course:
            raise ValueError("课程不存在，无法解析课程资料")
        f = self.db.get(CourseFile, file_id)
        if not f:
            raise ValueError("课程资料不存在，无法执行解析")
        # course_id 和 file_id 都来自任务输入，必须在任何状态更新、分块、
        # 章节或知识点写入之前校验对象归属，避免跨课程资料污染知识库。
        if f.course_id != course.id:
            raise ValueError("课程资料不属于当前课程，已拒绝跨课程解析")

        f.parse_status = "parsing"
        f.indexed = False
        f.parse_summary = "正在提取正文并清洗课程资料"
        self.db.commit()

        pages = parse_file(f.stored_path)
        if not pages:
            f.parse_status = "failed"
            f.parse_summary = "未提取到可用文本。若为扫描版 PDF，请先进行 OCR 或上传可复制文本版本。"
            f.indexed = False
            self.db.commit()
            raise ValueError(f.parse_summary)
        chunks_raw = chunk_pages(pages)
        if not chunks_raw:
            f.parse_status = "failed"
            f.parse_summary = "文档文本过短，无法形成有效检索片段。"
            f.indexed = False
            self.db.commit()
            raise ValueError(f.parse_summary)
        f.parse_status = "indexing"
        f.parse_summary = f"已提取 {len(pages)} 页，正在建立课程检索片段"
        self.db.commit()
        # 写入 DB
        self.db.query(DocumentChunk).filter(DocumentChunk.file_id == file_id).delete()
        self.db.commit()
        chunks_obj = []
        for idx, c in enumerate(chunks_raw):
            obj = DocumentChunk(course_id=course_id, file_id=file_id, chunk_index=idx,
                                text=c["text"], page=c.get("page", 1), source_name=f.filename,
                                tokens=len(c["text"]))
            self.db.add(obj)
            chunks_obj.append(obj)
        self.db.commit()

        sample = "\n\n".join(c["text"][:900] for c in chunks_raw[:10])
        system, prompt = course_parse_prompt(
            course.name if course else "当前课程",
            f.filename,
            sample,
        )
        parsed = llm_client.chat_json(
            prompt,
            system=system,
            purpose=self.purpose,
            trace_id=self.trace_id,
            max_tokens=2400,
        )

        # 写章节
        chapters = parsed.get("chapters") or []
        for i, ch in enumerate(chapters[:8]):
            title = str(ch.get("title") or f"章节{i + 1}").strip()[:128]
            exists = self.db.query(CourseChapter).filter(
                CourseChapter.course_id == course_id,
                CourseChapter.title == title,
            ).first()
            if exists:
                exists.summary = str(ch.get("summary") or exists.summary)[:500]
                continue
            self.db.add(CourseChapter(course_id=course_id, title=title,
                                       summary=str(ch.get("summary") or "")[:500], order_index=i))
        # 写知识点（若 LLM 没给则用启发式从 chunk 抽词）
        existing_points = self.db.query(KnowledgePoint).filter(
            KnowledgePoint.course_id == course_id
        ).all()
        pts = parsed.get("points") or []
        if not pts:
            pts = self._heuristic_points(chunks_raw)
        points_to_insert = pts if len(existing_points) < 5 else []
        for p in points_to_insert[:30]:
            name = (p.get("name") or "").strip()
            if not self._valid_point_name(name):
                continue
            exists = self.db.query(KnowledgePoint).filter(
                KnowledgePoint.course_id == course_id, KnowledgePoint.name == name).first()
            if exists:
                continue
            self.db.add(KnowledgePoint(course_id=course_id, name=name,
                                        description=p.get("description", "") or p.get("summary", "") or name,
                                        keywords=p.get("keywords", ""),
                                        difficulty=int(p.get("difficulty", 3))))
        self.db.commit()

        chapter_count = self.db.query(CourseChapter).filter(
            CourseChapter.course_id == course_id
        ).count()
        point_count = self.db.query(KnowledgePoint).filter(
            KnowledgePoint.course_id == course_id
        ).count()
        f.parse_status = "parsed"
        f.parse_summary = (
            f"解析 {len(pages)} 页，形成 {len(chunks_raw)} 个检索片段；"
            f"课程当前包含章节 {chapter_count}、知识点 {point_count}。"
        )
        f.indexed = True
        self.db.commit()

        return {"parsed": True, "pages": len(pages), "chunks": len(chunks_raw),
                "chapters": chapter_count, "points": point_count,
                "summary": f.parse_summary}

    @staticmethod
    def _valid_point_name(name: str) -> bool:
        if not (2 <= len(name) <= 18):
            return False
        blocked = (
            "可以用于", "不能简单", "当前任务", "的一条", "相关内容", "本文", "系统会",
            "本课程把", "定义为", "需要完成", "必须能够", "后仍可", "不允许", "由独立",
        )
        return not name.startswith(("与", "和", "及", "把", "由", "为")) and not any(
            part in name for part in blocked
        )

    def _heuristic_points(self, chunks):
        """领域无关的中文术语兜底，不再绑定计算机课程。"""
        import re
        from collections import Counter
        stop = {"课程", "内容", "资料", "进行", "以及", "通过", "可以", "需要", "主要", "本文", "系统"}
        counter: Counter[str] = Counter()
        for chunk in chunks:
            text = chunk["text"]
            headings = re.findall(r"(?:^|\n)\s*(?:第[一二三四五六七八九十\d]+[章节篇]|#+)\s*([^\n]{2,18})", text)
            terms = re.findall(r"[一-龥]{2,10}|[A-Za-z][A-Za-z0-9_-]{2,24}", text)
            counter.update(term.strip(" ：:") for term in headings + terms if term not in stop)
        return [
            {"name": name, "description": f"资料中的高频核心概念：{name}", "keywords": name,
             "difficulty": min(5, 2 + index // 5)}
            for index, (name, _) in enumerate(counter.most_common(18))
            if 2 <= len(name) <= 18
        ]
