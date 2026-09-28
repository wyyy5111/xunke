"""学习/教学报告导出：Markdown / PDF。"""
from __future__ import annotations
import io
import json
import re
from html import escape
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.profile import StudentProfile, KnowledgeMastery
from app.models.knowledge import KnowledgePoint
from app.models.test import PreTest, PostTest, TestAnswer
from app.models.question import Question
from app.models.learning import WrongQuestion, LearningPath, LearningRecord
from app.models.user import User
from app.utils.logger import logger


def build_student_markdown(db: Session, student_id: int, course_id: int) -> str:
    user = db.get(User, student_id)
    course = db.get(Course, course_id)
    if not user:
        raise ValueError("学生不存在")
    if not course:
        raise ValueError("课程不存在")
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id, StudentProfile.course_id == course_id).first()
    pre = db.query(PreTest).filter(PreTest.student_id == student_id,
                                   PreTest.course_id == course_id).order_by(PreTest.id.desc()).first()
    post = db.query(PostTest).filter(PostTest.student_id == student_id,
                                     PostTest.course_id == course_id).order_by(PostTest.id.desc()).first()
    mastery = db.query(KnowledgeMastery, KnowledgePoint).join(
        KnowledgePoint, KnowledgePoint.id == KnowledgeMastery.kp_id).filter(
        KnowledgeMastery.student_id == student_id, KnowledgeMastery.course_id == course_id).all()
    wrongs = db.query(WrongQuestion).filter(
        WrongQuestion.student_id == student_id, WrongQuestion.course_id == course_id,
        WrongQuestion.resolved == False).count()
    path = db.query(LearningPath).filter(
        LearningPath.student_id == student_id,
        LearningPath.course_id == course_id,
    ).first()
    records = db.query(LearningRecord).filter(
        LearningRecord.student_id == student_id,
        LearningRecord.course_id == course_id,
    ).all()
    learning_minutes = round(sum(max(0, r.duration or 0) for r in records) / 60)
    practice_count = sum(1 for r in records if r.action == "practice")

    md = []
    md.append(f"# 《{course.name}》个人学习报告\n")
    md.append(f"- 学生：{user.full_name or user.username}（{user.student_no or '-'}）\n")
    md.append(f"- 课程：{course.name}\n")
    md.append(f"- 生成时间：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}\n\n")

    md.append("## 一、学习概览\n")
    pre_s = pre.score if pre else 0
    post_s = post.score if post else 0
    md.append(f"- 前测成绩：**{pre_s}** 分\n")
    md.append(f"- 后测成绩：**{post_s}** 分\n")
    md.append(f"- 成绩提升：**{round(post_s - pre_s, 1)}** 分\n")
    md.append(f"- 未解决错题：{wrongs} 题\n\n")
    md.append(f"- 已完成学习节点：{path.completed_nodes if path else 0} 个\n")
    md.append(f"- 累计记录学习时长：{learning_minutes} 分钟\n")
    md.append(f"- 练习提交次数：{practice_count} 次\n\n")

    md.append("## 二、知识点掌握度\n")
    md.append("| 知识点 | 前测 | 后测 | 状态 |\n|---|---|---|---|\n")
    kp_names = {}
    post_by_kp = _post_kp_map(post)
    assessed_kp_ids = _assessed_kp_ids(db, post)
    for m, kp in mastery:
        kp_names[kp.id] = kp.name
        detail = post_by_kp.get(kp.id)
        assessed = bool(post) and (
            kp.id in assessed_kp_ids
            if assessed_kp_ids
            else bool(detail and detail.get("assessed", detail.get("post") is not None))
        )
        if assessed and detail is not None:
            pre_value = detail.get("pre", m.pre_score)
            post_value = detail.get("post", m.post_score)
            status_label = _score_status_label(post_value)
        elif post:
            # 后测未覆盖的知识点必须标为待复测，不能把沿用的前测值
            # 冒充新的后测证据。
            pre_value = m.pre_score
            post_value = "待复测"
            status_label = "待复测"
        else:
            pre_value = m.pre_score
            post_value = m.post_score if post else "待复测"
            status_label = (
                _score_status_label(post_value)
                if post
                else _mastery_status_label(m.status)
            )
        md.append(
            f"| {kp.name} | {pre_value} | {post_value} | {status_label} |\n"
        )
    md.append("\n")

    md.append("## 三、学习建议\n")
    pending_names: list[str] = []
    if post:
        mastered_names: list[str] = []
        reinforce_names: list[str] = []
        for mastery_row, kp in mastery:
            if assessed_kp_ids and kp.id not in assessed_kp_ids:
                pending_names.append(kp.name)
                continue
            detail = post_by_kp.get(kp.id) or {}
            if detail.get("assessed") is False:
                pending_names.append(kp.name)
                continue
            score = detail.get("post", mastery_row.post_score)
            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                pending_names.append(kp.name)
                continue
            (mastered_names if numeric_score >= 80 else reinforce_names).append(kp.name)
        md.append(
            f"本次后测覆盖 {len(mastered_names) + len(reinforce_names)} 个知识点，"
            f"其中 {len(mastered_names)} 个达到已掌握。"
        )
        if reinforce_names:
            md.append(f"建议继续补强：{', '.join(reinforce_names[:5])}。")
        if pending_names:
            md.append(
                f"另有 {len(pending_names)} 个知识点未被本次后测覆盖，"
                f"建议通过专项练习复测：{', '.join(pending_names[:5])}。"
            )
    elif profile:
        md.append(profile.recommendation or "继续巩固薄弱知识点。\n")
    md.append("\n")

    md.append("## 四、提升路径\n")
    if post and post.by_kp:
        try:
            for it in json.loads(post.by_kp):
                try:
                    point_id = int(it.get("kp_id"))
                except (TypeError, ValueError):
                    point_id = 0
                if (
                    (assessed_kp_ids and point_id not in assessed_kp_ids)
                    or it.get("assessed") is False
                    or it.get("post") is None
                ):
                    continue
                label = kp_names.get(point_id) or it.get("name") or "课程知识点"
                md.append(f"- {label}：{it.get('pre')} → {it.get('post')}（提升 {it.get('improvement')}）\n")
        except Exception as exc:
            logger.debug("后测知识点明细无法解析，报告已跳过该段：%s", exc)
    if pending_names:
        md.append(f"- 待复测：{', '.join(pending_names)}\n")

    return "".join(md)


def _mastery_status_label(status: str) -> str:
    return {
        "mastered": "已掌握",
        "consolidated": "巩固中",
        "weak": "待强化",
    }.get(str(status or "").lower(), "待评估")


def _score_status_label(score: object) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "待评估"
    if value >= 80:
        return "已掌握"
    if value >= 60:
        return "巩固中"
    return "待强化"


def _post_kp_map(post: PostTest | None) -> dict[int, dict]:
    if not post or not post.by_kp:
        return {}
    try:
        rows = json.loads(post.by_kp)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    result: dict[int, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            kp_id = int(row.get("kp_id"))
        except (TypeError, ValueError):
            continue
        result[kp_id] = row
    return result


def _assessed_kp_ids(db: Session, post: PostTest | None) -> set[int]:
    if not post:
        return set()
    rows = db.query(Question.kp_id).join(
        TestAnswer, TestAnswer.question_id == Question.id
    ).filter(
        TestAnswer.student_id == post.student_id,
        TestAnswer.course_id == post.course_id,
        TestAnswer.test_type == "post",
        TestAnswer.test_id == post.id,
        Question.kp_id.is_not(None),
    ).distinct().all()
    return {int(kp_id) for (kp_id,) in rows if kp_id is not None}


def build_class_markdown(db: Session, course_id: int) -> str:
    course = db.get(Course, course_id)
    if not course:
        raise ValueError("课程不存在")
    students = db.query(StudentProfile).filter(StudentProfile.course_id == course_id).all()
    md = []
    md.append(f"# 《{course.name}》班级教学分析报告\n")
    md.append(f"- 生成时间：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}\n")
    md.append(f"- 参与学生：{len(students)} 人\n\n")

    md.append("## 一、班级整体\n")
    completed = [s for s in students if float(s.post_score or 0) > 0]
    compared = completed or students
    pre_avg = sum(s.pre_score for s in compared) / max(1, len(compared))
    post_avg = sum(s.post_score for s in completed) / max(1, len(completed)) if completed else 0
    md.append(f"- 平均前测：{round(pre_avg, 1)}\n")
    md.append(f"- 已完成后测：{len(completed)} 人\n")
    md.append(f"- 平均后测：{round(post_avg, 1) if completed else '尚无数据'}\n")
    md.append(f"- 平均提升：{round(post_avg - pre_avg, 1) if completed else '尚无数据'}\n\n")

    md.append("## 二、薄弱知识点热力\n")
    weak_counter = {}
    point_names = dict(db.query(KnowledgePoint.id, KnowledgePoint.name).filter(
        KnowledgePoint.course_id == course_id,
    ).all())
    for s in students:
        try:
            for it in json.loads(s.weak_points):
                try:
                    point_id = int(it.get("id") or it.get("kp_id") or 0)
                except (TypeError, ValueError):
                    point_id = 0
                name = point_names.get(point_id) or it.get("name", "")
                if name:
                    weak_counter[name] = weak_counter.get(name, 0) + 1
        except Exception as exc:
            logger.debug("学生画像薄弱点无法解析，班级报告已跳过该条：%s", exc)
    md.append("| 知识点 | 薄弱人数 |\n|---|---|\n")
    for name, cnt in sorted(weak_counter.items(), key=lambda x: -x[1])[:15]:
        md.append(f"| {name} | {cnt} |\n")

    return "".join(md)


def md_to_html(md: str) -> str:
    """Markdown -> 带样式的完整 HTML（用于在线预览 / 浏览器打印 PDF）。"""
    try:
        import markdown2
        html = markdown2.markdown(
            md,
            extras=["tables", "fenced-code-blocks"],
            safe_mode="escape",
        )
    except Exception:
        # markdown2 缺失时做最简单的转换
        html = (md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                 .replace("\n\n", "</p><p>").replace("\n", "<br>"))
        html = f"<p>{html}</p>"
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'\">"
        "<style>"
        "body{font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif; padding:40px; max-width:900px; margin:0 auto; color:#1f2937; line-height:1.8;}"
        "h1{color:#4f46e5;border-bottom:3px solid #6366f1;padding-bottom:8px;}"
        "h2{color:#4f46e5;border-left:4px solid #6366f1;padding-left:12px;margin-top:24px;}"
        "h3{color:#6366f1;}"
        "table{border-collapse:collapse;width:100%;margin:12px 0;}"
        "th,td{border:1px solid #cbd5e1;padding:8px 12px;text-align:left;}"
        "th{background:#f1f5f9;font-weight:600;}"
        "tr:nth-child(even){background:#f8fafc;}"
        "code{background:#f1f5f9;padding:2px 6px;border-radius:4px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:13px;color:#dc2626;}"
        "pre{background:#1e293b;color:#e2e8f0;padding:14px;border-radius:8px;overflow-x:auto;}"
        "pre code{background:transparent;color:inherit;padding:0;}"
        "blockquote{border-left:4px solid #818cf8;padding-left:16px;color:#64748b;margin:12px 0;background:#f8fafc;padding:12px 16px;border-radius:0 8px 8px 0;}"
        "ul,ol{padding-left:24px;}"
        "li{margin:4px 0;}"
        "hr{border:none;border-top:2px dashed #cbd5e1;margin:20px 0;}"
        "</style></head><body>" + html + "</body></html>"
    )


def md_to_pdf_bytes(md: str) -> tuple[bytes, bool]:
    """Markdown -> PDF bytes。返回 (data, is_pdf)。

    优先 WeasyPrint；不可用时使用 ReportLab 的内置中文 CID 字体生成
    真实 PDF。只有两种 PDF 引擎都不可用时才退回 HTML 打印预览。
    """
    html = md_to_html(md)
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf(), True
    except Exception:
        try:
            return _reportlab_pdf(md), True
        except Exception:
            return html.encode("utf-8"), False


def _reportlab_pdf(md: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    except Exception as exc:
        logger.debug("中文 PDF 字体已注册或不可重复注册：%s", exc)
    font = "STSong-Light"
    styles = getSampleStyleSheet()
    body = ParagraphStyle("CNBody", parent=styles["BodyText"], fontName=font,
                          fontSize=10.5, leading=17, textColor=colors.HexColor("#1f2937"),
                          spaceAfter=4)
    h1 = ParagraphStyle("CNH1", parent=body, fontSize=20, leading=28, alignment=TA_CENTER,
                        textColor=colors.HexColor("#3730a3"), spaceAfter=14)
    h2 = ParagraphStyle("CNH2", parent=body, fontSize=15, leading=22,
                        textColor=colors.HexColor("#4338ca"), spaceBefore=10, spaceAfter=7)
    h3 = ParagraphStyle("CNH3", parent=body, fontSize=12.5, leading=19,
                        textColor=colors.HexColor("#4f46e5"), spaceBefore=7, spaceAfter=5)
    bullet = ParagraphStyle("CNBullet", parent=body, leftIndent=12, firstLineIndent=-8)
    table_style = ParagraphStyle("CNTable", parent=body, fontSize=9, leading=13)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                            topMargin=17 * mm, bottomMargin=17 * mm,
                            title="XunkeFlow 学习报告")
    story = []
    lines = md.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        if not raw:
            story.append(Spacer(1, 3 * mm))
            index += 1
            continue
        if raw.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = []
            for line in table_lines:
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    continue
                rows.append([Paragraph(_inline_markdown(cell), table_style) for cell in cells])
            if rows:
                width = (A4[0] - 36 * mm) / max(1, len(rows[0]))
                table = Table(rows, colWidths=[width] * len(rows[0]), repeatRows=1)
                table.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#312e81")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.extend([table, Spacer(1, 3 * mm)])
            continue
        if raw.startswith("# "):
            story.append(Paragraph(_inline_markdown(raw[2:]), h1))
        elif raw.startswith("## "):
            story.append(Paragraph(_inline_markdown(raw[3:]), h2))
        elif raw.startswith("### "):
            story.append(Paragraph(_inline_markdown(raw[4:]), h3))
        elif re.match(r"^[-*]\s+", raw):
            story.append(Paragraph("- " + _inline_markdown(raw[2:]), bullet))
        else:
            story.append(Paragraph(_inline_markdown(raw), body))
        index += 1

    doc.build(
        story,
        onFirstPage=_draw_report_footer,
        onLaterPages=_draw_report_footer,
    )
    return buffer.getvalue()


def _inline_markdown(text: str) -> str:
    # ReportLab 的内置 STSong CID 字体不能稳定覆盖 U+00B7/U+2022，
    # 未归一化时会在中文报告中渲染为方框。PDF 输出使用 ASCII 连字符，
    # 原始 Markdown/HTML 内容保持不变。
    normalized = text.replace("·", "-").replace("•", "-")
    safe = escape(normalized)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"`(.+?)`", r"<font color='#4338ca'>\1</font>", safe)
    return safe


def _draw_report_footer(canvas, doc) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 8 * mm, "XunkeFlow")
    canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()
