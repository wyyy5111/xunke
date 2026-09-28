"""Evidence-aware resource quality scoring."""
from __future__ import annotations
import re
from typing import List
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgePoint
from app.models.quality import QualityReport
from app.models.resource import GeneratedResource


def score_resource(db: Session, resource: GeneratedResource,
                   kps: List[KnowledgePoint], citations: list[dict],
                   course_id: int) -> QualityReport:
    content = resource.content or ""
    # 1. Knowledge coverage. A focused resource is evaluated against its target
    # knowledge point rather than against every point in the course.
    target_kps = [kp for kp in kps if resource.kp_id and kp.id == resource.kp_id]
    if not target_kps:
        target_kps = kps[: min(6, len(kps))]
    kp_hit = 0
    for kp in target_kps:
        if kp.name in content or any(k.strip() and k.strip() in content for k in (kp.keywords or "").split(",")):
            kp_hit += 1
    coverage = min(1.0, kp_hit / max(1, len(target_kps)))

    # 2. Citation hit + lexical groundedness.
    valid_cites = [c for c in citations if c.get("snippet") and float(c.get("score", 0) or 0) >= 0.05]
    citation_hit = len(valid_cites) / max(1, len(citations)) if citations else 0.0
    citation_terms = set()
    for cite in valid_cites:
        citation_terms.update(re.findall(r"[一-龥]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,20}", cite.get("snippet", "")))
    content_terms = set(re.findall(r"[一-龥]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,20}", content))
    groundedness = len(citation_terms & content_terms) / max(1, min(len(citation_terms), 40)) if citation_terms else 0.0
    citation_hit = min(1.0, citation_hit * 0.65 + groundedness * 0.35)

    # 3. 答案一致性（题类）：含 answer 字段且非空
    answer_consistency = 0.88
    parsed_questions = []
    if resource.rtype == "exercise":
        try:
            import json
            data = json.loads(content)
            parsed_questions = data.get("questions", []) if isinstance(data, dict) else []
            if parsed_questions:
                ok = 0
                for q in parsed_questions:
                    answer = str(q.get("answer") or "").strip()
                    analysis = str(q.get("analysis") or "").strip()
                    if not answer or not analysis:
                        continue
                    if q.get("qtype") == "single":
                        options = q.get("options") or []
                        correct_keys = [str(opt.get("key")) for opt in options if opt.get("is_correct")]
                        if len(correct_keys) != 1 or answer != correct_keys[0]:
                            continue
                    ok += 1
                answer_consistency = ok / len(parsed_questions)
        except Exception:
            answer_consistency = 0.7

    # 4. Difficulty validity.
    if parsed_questions:
        valid_difficulty = sum(1 for q in parsed_questions if 1 <= int(q.get("difficulty") or 0) <= 5)
        difficulty_match = valid_difficulty / len(parsed_questions)
    else:
        difficulty_match = 0.82 if len(content) >= 300 else 0.55

    # 5. Structure completeness: course-agnostic; code is never mandatory.
    structure = 0.0
    if re.search(r"^#+\s", content, re.M):
        structure += 0.3
    if re.search(r"^\s*[-*]\s", content, re.M):
        structure += 0.3
    if re.search(r"\*\*[^*]+\*\*", content):
        structure += 0.15
    if "|" in content and "---" in content:
        structure += 0.15
    if parsed_questions:
        structure = max(structure, 0.8)
    if len(content) >= 500:
        structure += 0.1
    structure = min(1.0, structure)

    # 6. Diversity is based on exercise types or instructional sections.
    if parsed_questions:
        diversity = min(1.0, len({q.get("qtype") for q in parsed_questions}) / 4)
    else:
        section_count = len(re.findall(r"^##+\s", content, re.M))
        diversity = min(1.0, 0.45 + section_count * 0.08)
    # 7. 重复比例：粗略计算重复行
    lines = [l for l in content.split("\n") if l.strip()]
    dup = 1 - len(set(lines)) / max(1, len(lines))
    duplicate = round(dup, 3)
    # 8. 风险比例：包含"绝对""一定""100%"等夸大词
    risk_patterns = [
        r"绝对(?!化|表述|措辞)",
        r"(?<!0-)100%",
        r"肯定(?:会|能|是)",
        r"毫无疑问",
        r"唯一正确",
        r"保证(?:收益|成功|通过)",
        r"必然(?:上涨|成功|有效)",
    ]
    risk = sum(1 for pattern in risk_patterns if re.search(pattern, content)) * 0.1
    risk = min(1.0, risk)

    # 综合
    score = (
        coverage * 0.18 + citation_hit * 0.24 + answer_consistency * 0.16 +
        difficulty_match * 0.10 + structure * 0.16 + diversity * 0.10 +
        (1 - duplicate) * 0.03 + (1 - risk) * 0.02
    ) * 100

    suggestions = []
    if coverage < 0.5:
        suggestions.append("知识点覆盖率偏低，建议补充更多知识点关键词。")
    if citation_hit < 0.5:
        suggestions.append("引用命中率不足，建议增加对课程资料的检索引用。")
    if structure < 0.6:
        suggestions.append("资源结构不够完整，建议补充层级标题、要点列表、例题或任务步骤。")
    if resource.rtype == "exercise" and answer_consistency < 1:
        suggestions.append("存在答案、正确选项或解析不一致，请修订后再发布。")
    if risk > 0:
        suggestions.append("存在夸大表述，请核对事实准确性。")

    rep = db.query(QualityReport).filter(QualityReport.resource_id == resource.id).first()
    if not rep:
        rep = QualityReport(resource_id=resource.id)
        db.add(rep)
    rep.coverage = round(coverage, 3)
    rep.citation_hit = round(citation_hit, 3)
    rep.answer_consistency = round(answer_consistency, 3)
    rep.difficulty_match = round(difficulty_match, 3)
    rep.structure = round(structure, 3)
    rep.diversity = round(diversity, 3)
    rep.duplicate = duplicate
    rep.risk = round(risk, 3)
    rep.score = round(score, 1)
    rep.suggestions = __import__("json").dumps(suggestions, ensure_ascii=False)
    resource.quality_score = round(score, 1)
    db.commit()
    return rep
