"""演示数据 seed：3 门课程 + 知识点 + 题库 + 学生 + 前测 + 画像 + 资源 + Agent 日志。

幂等：通过 SystemConfig 标记是否已 seed。
"""
from __future__ import annotations
import json
from datetime import timedelta

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.course import Course, CourseChapter, CourseFile, CourseEnrollment
from app.models.knowledge import KnowledgePoint, KnowledgeRelation
from app.models.profile import StudentProfile, KnowledgeMastery
from app.models.question import Question, QuestionOption
from app.models.test import PreTest, PostTest, TestAnswer
from app.models.resource import GeneratedResource, ResourceReview
from app.models.learning import LearningPath, LearningRecord, WrongQuestion
from app.models.agent import AgentRun, AgentLog
from app.models.chunk import DocumentChunk
from app.models.system import SystemConfig
from app.utils.time_util import safe_json_dumps, utc_now

SEED_FLAG = "seed_v1_done"

# Cross-disciplinary demonstration catalog. These courses intentionally avoid a
# computer-science-only demo so judges can see the platform adapt to real course material.
FINANCE_KPS = [
    ("银行人工智能应用边界", "识别辅助决策、客户服务与高风险业务之间的责任边界", 2, 0.9, "银行人工智能,应用边界,辅助决策"),
    ("模型风险", "理解模型错误、偏差、漂移与不当使用带来的业务风险", 3, 1.0, "模型风险,偏差,漂移"),
    ("知识库忠实性", "检查生成结论是否得到检索证据支持", 4, 1.0, "知识库,证据,忠实性"),
    ("证据冲突与时效", "识别制度版本冲突、过期证据与适用范围差异", 4, 0.9, "证据冲突,制度时效,版本"),
    ("金融消费者权益保护", "理解知情权、自主选择权与公平交易要求", 3, 1.0, "消费者权益,知情权,公平交易"),
    ("产品适当性", "把客户风险承受能力与产品风险等级进行匹配", 4, 1.0, "产品适当性,风险承受能力,匹配"),
    ("隐私与敏感信息保护", "识别个人信息、敏感字段与最小必要处理原则", 3, 1.0, "个人信息,隐私,敏感字段"),
    ("工具权限矩阵", "为智能体工具与业务动作设置角色、范围和条件", 4, 0.8, "工具权限,角色,授权"),
    ("高风险动作分级", "按照影响范围与可逆性划分动作风险等级", 4, 0.9, "高风险动作,分级,可逆性"),
    ("审计证据链", "串联输入、检索、生成、工具、人工复核与处置记录", 4, 1.0, "审计证据链,追溯,留痕"),
    ("人工复核与责任边界", "明确模型建议、业务审批、合规复核的责任分工", 3, 1.0, "人工复核,责任边界,审批"),
    ("复测与整改闭环", "将问题发现、修订、复测和版本确认形成闭环", 3, 0.9, "复测,整改,闭环"),
]
FINANCE_PREREQ = [
    ("模型风险", "银行人工智能应用边界"),
    ("知识库忠实性", "模型风险"),
    ("证据冲突与时效", "知识库忠实性"),
    ("产品适当性", "金融消费者权益保护"),
    ("高风险动作分级", "工具权限矩阵"),
    ("审计证据链", "知识库忠实性"),
    ("审计证据链", "工具权限矩阵"),
    ("人工复核与责任边界", "审计证据链"),
    ("复测与整改闭环", "人工复核与责任边界"),
]

LITERATURE_KPS = [
    ("先秦诗歌传统", "理解诗经与楚辞的表达传统", 2, 0.8, "诗经,楚辞,诗歌传统"),
    ("汉魏风骨", "把握汉乐府与建安文学的时代精神", 3, 0.8, "汉乐府,建安文学,风骨"),
    ("唐诗意象", "分析唐诗中意象、情感与语境的关系", 3, 1.0, "唐诗,意象,情感"),
    ("宋词词境", "理解婉约与豪放词风及其表达边界", 3, 0.9, "宋词,婉约,豪放"),
    ("古典叙事视角", "识别叙述者、视角与人物塑造方式", 4, 0.9, "叙事视角,叙述者,人物"),
    ("修辞与章法", "分析比兴、用典、对偶与篇章结构", 3, 0.9, "比兴,用典,对偶,章法"),
    ("作品细读方法", "使用文本证据完成词句、结构与主题分析", 4, 1.0, "细读,文本证据,主题"),
    ("文学史语境", "把作品放入作者经历与时代语境中解释", 4, 0.8, "文学史,时代语境,作者"),
    ("审美判断表达", "形成有证据、有边界的文学鉴赏观点", 4, 0.9, "审美判断,鉴赏,证据"),
    ("比较阅读", "比较不同作品的主题、意象与表达策略", 5, 0.8, "比较阅读,主题,表达策略"),
]
LITERATURE_PREREQ = [
    ("唐诗意象", "先秦诗歌传统"),
    ("宋词词境", "唐诗意象"),
    ("作品细读方法", "修辞与章法"),
    ("审美判断表达", "作品细读方法"),
    ("文学史语境", "作品细读方法"),
    ("比较阅读", "审美判断表达"),
]

ENTREPRENEUR_KPS = [
    ("用户问题识别", "从真实情境中识别未满足需求与关键痛点", 2, 1.0, "用户问题,需求,痛点"),
    ("价值主张", "说明方案为谁创造什么可验证价值", 3, 1.0, "价值主张,目标用户,价值"),
    ("利益相关者", "识别用户、合作方、管理者与监管等主体", 3, 0.8, "利益相关者,角色,诉求"),
    ("市场与竞品分析", "用证据比较市场空间、替代方案与差异化", 4, 0.9, "市场分析,竞品,差异化"),
    ("商业模式", "设计价值创造、交付与收益实现机制", 4, 1.0, "商业模式,价值交付,收益"),
    ("最小可行产品", "用最小成本验证最关键假设", 3, 1.0, "最小可行产品,MVP,验证"),
    ("实验与指标", "定义假设、实验、成功指标与停止条件", 4, 0.9, "实验,指标,假设"),
    ("项目计划与风险", "拆解里程碑、资源、依赖与风险应对", 3, 0.9, "项目计划,里程碑,风险"),
    ("财务可行性", "估算成本、收入、现金流与敏感性", 4, 0.8, "成本,收入,现金流"),
    ("路演表达", "用问题、证据、方案、验证和行动形成叙事", 3, 0.8, "路演,叙事,证据"),
]
ENTREPRENEUR_PREREQ = [
    ("价值主张", "用户问题识别"),
    ("市场与竞品分析", "价值主张"),
    ("商业模式", "价值主张"),
    ("最小可行产品", "价值主张"),
    ("实验与指标", "最小可行产品"),
    ("项目计划与风险", "实验与指标"),
    ("财务可行性", "商业模式"),
    ("路演表达", "市场与竞品分析"),
]

# 课程配置：把三门课的数据统一组织，便于循环处理
COURSES_CONFIG = [
    {
        "name": "银行人工智能治理与合规审计", "code": "EDU301", "teacher_key": "teacher",
        "desc": "围绕银行人工智能应用边界、证据忠实性、消费者保护、工具权限和审计闭环开展案例化学习。",
        "tags": "金融治理,合规审计,人工智能", "domain": "银行人工智能治理",
        "chapters": [
            ("第1章 银行人工智能应用与风险", "应用边界、模型风险与责任主体"),
            ("第2章 证据忠实性审计", "知识库依据、冲突与时效"),
            ("第3章 消费者保护与隐私", "产品适当性、权益与敏感信息"),
            ("第4章 智能体工具治理", "权限矩阵与高风险动作"),
            ("第5章 审计闭环", "证据链、人工复核、复测整改"),
        ],
        "kps": FINANCE_KPS, "prereq": FINANCE_PREREQ,
        "sim_pairs": [("知识库忠实性", "证据冲突与时效")],
        "confuse_pairs": [("模型风险", "高风险动作分级")],
        "lecture_file": "finance_governance/lecture.md",
        "demo_topics": ["知识库忠实性", "产品适当性", "审计证据链"],
    },
    {
        "name": "中国古代文学经典导读", "code": "EDU302", "teacher_key": "teacher2",
        "desc": "通过文本细读、文学史语境和比较阅读，形成有证据的古典文学鉴赏能力。",
        "tags": "中国文学,文本细读,审美表达", "domain": "中国古代文学",
        "chapters": [
            ("第1章 诗歌传统", "先秦、汉魏与唐诗的表达传统"),
            ("第2章 唐诗与宋词", "意象、词境与审美风格"),
            ("第3章 古典叙事", "叙事视角与人物塑造"),
            ("第4章 文本细读", "修辞、章法与证据表达"),
            ("第5章 比较阅读", "文学史语境与跨作品比较"),
        ],
        "kps": LITERATURE_KPS, "prereq": LITERATURE_PREREQ,
        "sim_pairs": [("唐诗意象", "宋词词境")],
        "confuse_pairs": [("文学史语境", "作品细读方法")],
        "lecture_file": "literature_course/lecture.md",
        "demo_topics": ["唐诗意象", "作品细读方法", "比较阅读"],
    },
    {
        "name": "大学生创新创业项目管理", "code": "EDU303", "teacher_key": "teacher",
        "desc": "从用户问题、价值主张到最小可行产品、商业模式、实验指标和路演表达的项目式课程。",
        "tags": "创新创业,项目管理,商业策划", "domain": "创新创业",
        "chapters": [
            ("第1章 发现问题", "用户研究、需求与利益相关者"),
            ("第2章 设计价值", "价值主张、市场与竞品"),
            ("第3章 验证方案", "最小可行产品与实验指标"),
            ("第4章 经营与交付", "商业模式、财务与项目风险"),
            ("第5章 路演与复盘", "证据化表达和迭代计划"),
        ],
        "kps": ENTREPRENEUR_KPS, "prereq": ENTREPRENEUR_PREREQ,
        "sim_pairs": [("价值主张", "商业模式")],
        "confuse_pairs": [("市场与竞品分析", "用户问题识别")],
        "lecture_file": "entrepreneurship_course/lecture.md",
        "demo_topics": ["价值主张", "最小可行产品", "实验与指标"],
    },
]


def ensure_seed():
    db = SessionLocal()
    try:
        _ensure_admin(db)
        flag = db.query(SystemConfig).filter(SystemConfig.key == SEED_FLAG).first()
        if flag and flag.value == "1":
            _ensure_featured_course(db)
            _ensure_demo_agent_run(db)
            return
        _seed(db)
        if not flag:
            db.add(SystemConfig(key=SEED_FLAG, value="1", category="general", remark="演示数据已初始化 v2"))
        else:
            flag.value = "1"
        db.commit()
    finally:
        db.close()


def _ensure_featured_course(db) -> None:
    """Add the cross-disciplinary catalog to older demo databases.

    Existing courses and user data are preserved; this is an additive, idempotent
    upgrade so an old workspace immediately has non-computer-science courses to show.
    """
    for cfg in COURSES_CONFIG:
        existing = db.query(Course).filter(
            (Course.code == cfg["code"]) | (Course.name == cfg["name"])
        ).first()
        if existing:
            existing.status = "active"
            db.commit()
            continue
        teacher = db.query(User).filter(User.username == cfg["teacher_key"]).first() or _ensure_admin(db)
        _create_featured_course(db, cfg, teacher)
    _ensure_demo_agent_run(db)


def _create_featured_course(db, cfg: dict, teacher: User) -> Course:
    course = _course(db, cfg["name"], cfg["code"], teacher.id, cfg["desc"], cfg["tags"])
    kp_map = {}
    for index, (title, summary) in enumerate(cfg["chapters"]):
        db.add(CourseChapter(course_id=course.id, title=title, summary=summary, order_index=index))
    for name, desc, diff, importance, keywords in cfg["kps"]:
        kp = KnowledgePoint(course_id=course.id, name=name, description=desc,
                            difficulty=diff, importance=importance, keywords=keywords)
        db.add(kp)
        db.flush()
        kp_map[name] = kp
        _add_single(db, course.id, kp.id, name, diff, cfg["domain"])
        _add_judge(db, course.id, kp.id, name, diff, cfg["domain"])
    for target_name, source_name in cfg["prereq"]:
        target, source = kp_map.get(target_name), kp_map.get(source_name)
        if target and source:
            db.add(KnowledgeRelation(course_id=course.id, source_id=source.id,
                                     target_id=target.id, relation="prerequisite"))
    db.commit()
    _index_demo_file(db, course.id, teacher.id, cfg["lecture_file"])

    students = db.query(User).filter(User.role == "student").order_by(User.id).limit(6).all()
    for index, student in enumerate(students):
        enrolled = db.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.student_id == student.id,
        ).first()
        if not enrolled:
            _enroll_and_test(db, student, course, kp_map, index)

    from app.services.builtin_generator import builtin
    from app.rag.retriever import retrieve, format_citations
    for topic_name in cfg["demo_topics"]:
        kp = kp_map[topic_name]
        cites = format_citations(retrieve(db, course.id, topic_name, top_k=4))
        context = "\n".join(item["snippet"] for item in cites)
        content = builtin.chat(
            f"课程名称：{course.name}\n知识点：{topic_name}\n<course_context>{context}</course_context>"
        )
        resource = GeneratedResource(
            course_id=course.id,
            kp_id=kp.id,
            rtype="lecture",
            title=f"{topic_name} · 证据型讲义",
            content=content,
            citations=safe_json_dumps(cites),
            quality_score=0,
            review_status="published",
            published=True,
        )
        db.add(resource)
        db.flush()
        from app.services.quality_service import score_resource
        score_resource(db, resource, list(kp_map.values()), cites, course.id)
    db.commit()
    return course


def _seed(db):
    # ---------- 用户 ----------
    _ensure_admin(db)
    teachers = {
        "teacher": _user(db, "teacher", "teacher@edu.cn", "王老师", "teacher", "金融治理与创新创业课程教师"),
        "teacher2": _user(db, "teacher2", "teacher2@edu.cn", "李老师", "teacher", "人文课程教师"),
    }
    students = []
    names = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
             "郑明", "冯雪", "陈晓", "褚健"]
    for i, n in enumerate(names, 1):
        students.append(_user(db, f"student{i:02d}", f"student{i:02d}@edu.cn", n,
                              "student", n, student_no=f"S2024{i:03d}"))

    # ---------- 三门课程统一构建 ----------
    course_objs = {}
    course_kp_maps = {}
    for cfg in COURSES_CONFIG:
        c = _course(db, cfg["name"], cfg["code"], teachers[cfg["teacher_key"]].id,
                    cfg["desc"], cfg["tags"])
        course_objs[cfg["name"]] = c
        # 章节
        for i, (t, s) in enumerate(cfg["chapters"]):
            db.add(CourseChapter(course_id=c.id, title=t, summary=s, order_index=i))
        # 知识点
        kp_map = {}
        for name, desc, diff, imp, kw in cfg["kps"]:
            kp = KnowledgePoint(course_id=c.id, name=name, description=desc,
                                difficulty=diff, importance=imp, keywords=kw)
            db.add(kp); db.flush()
            kp_map[name] = kp
        course_kp_maps[cfg["name"]] = kp_map
        db.commit()
        # 先修关系
        for a, b in cfg["prereq"]:
            if a in kp_map and b in kp_map:
                db.add(KnowledgeRelation(course_id=c.id, source_id=kp_map[a].id,
                                         target_id=kp_map[b].id, relation="prerequisite"))
        for a, b in cfg["sim_pairs"]:
            if a in kp_map and b in kp_map:
                db.add(KnowledgeRelation(course_id=c.id, source_id=kp_map[a].id,
                                         target_id=kp_map[b].id, relation="相似", weight=0.6))
        for a, b in cfg["confuse_pairs"]:
            if a in kp_map and b in kp_map:
                db.add(KnowledgeRelation(course_id=c.id, source_id=kp_map[a].id,
                                         target_id=kp_map[b].id, relation="易混", weight=0.8))
        # 题库（每知识点 1 单选 + 1 判断）
        for name, _, diff, _, _ in cfg["kps"]:
            kp = kp_map[name]
            _add_single(db, c.id, kp.id, name, diff, cfg["domain"])
            _add_judge(db, c.id, kp.id, name, diff, cfg["domain"])
        db.commit()

        # 预置课程资料文件 + 解析为 chunk + 建向量索引
        _index_demo_file(db, c.id, teachers[cfg["teacher_key"]].id, cfg["lecture_file"])

    course_names = [cfg["name"] for cfg in COURSES_CONFIG]
    # ---------- 学生选课 + 前测 + 画像 ----------
    for s in students:
        _enroll_and_test(db, s, course_objs[course_names[0]], course_kp_maps[course_names[0]], 0)
        if int(s.username.replace("student", "")) <= 6:
            _enroll_and_test(db, s, course_objs[course_names[1]], course_kp_maps[course_names[1]], 1)
        if int(s.username.replace("student", "")) <= 4:
            _enroll_and_test(db, s, course_objs[course_names[2]], course_kp_maps[course_names[2]], 2)

    # ---------- 学习路径 ----------
    for s in students[:6]:
        for cname in course_names[:2]:
            kp_list = list(course_kp_maps[cname].values())[:8]
            nodes = [{"order": i + 1, "kp_id": k.id, "name": k.name, "difficulty": k.difficulty,
                      "mastery": 50, "estimated_minutes": 30, "status": "done" if i < 3 else "pending"}
                     for i, k in enumerate(kp_list)]
            db.add(LearningPath(student_id=s.id, course_id=course_objs[cname].id,
                                nodes=safe_json_dumps(nodes), total_minutes=240, completed_nodes=3))

    # ---------- 资源（用内置生成器为每门课的代表性知识点生成讲义/练习/PPT） ----------
    _seed_resources(db, course_objs, course_kp_maps)

    # A fresh offline installation must have a truthful, inspectable command
    # center before the first live run. This record is explicitly marked as
    # preloaded demonstration evidence in both its payload and the frontend.
    _seed_agent_logs(db, course_objs[course_names[0]].id, students[0].id)

    db.commit()


def _enroll_and_test(db, student, course, kp_map, idx_seed):
    """学生选课 + 前测 + 画像 + 部分后测。"""
    db.add(CourseEnrollment(course_id=course.id, student_id=student.id,
                            goal=f"掌握{course.name}核心原理", weekly_hours=6 + (idx_seed % 4)))
    all_qs = db.query(Question).filter(Question.course_id == course.id).all()
    if not all_qs:
        return
    picked = all_qs[:10]
    correct_n = 3 + (idx_seed % 6)
    answers = []
    for j, q in enumerate(picked):
        ok = j < correct_n
        ans = q.answer if ok else _wrong_of(q.answer)
        answers.append((q, ans, ok))
    score = round(correct_n / max(1, len(picked)) * 100, 1)
    pt = PreTest(student_id=student.id, course_id=course.id,
                 question_ids=safe_json_dumps([q.id for q, _, _ in answers]),
                 total=len(picked), correct=correct_n, score=score,
                 finished_at=utc_now() - timedelta(days=5),
                 diagnosis=safe_json_dumps({"level": "basic" if score < 60 else "intermediate"}))
    db.add(pt); db.flush()
    for q, ans, ok in answers:
        db.add(TestAnswer(student_id=student.id, course_id=course.id, test_type="pre",
                          test_id=pt.id, question_id=q.id, answer=ans, is_correct=ok))
        if not ok and q.kp_id:
            db.add(WrongQuestion(student_id=student.id, course_id=course.id,
                                 question_id=q.id, kp_id=q.kp_id, wrong_answer=ans, reason="概念不清"))
    # 画像
    rng_kp = list(kp_map.values())
    prof = StudentProfile(student_id=student.id, course_id=course.id, stage="learning",
                          goal="通过考试", weekly_hours=6, pre_score=score,
                          base_level="basic" if score < 60 else ("intermediate" if score < 85 else "advanced"),
                          pref_style="理解型" if idx_seed % 2 == 0 else "实践型",
                          pref_format="图解,案例,短练习",
                          learning_speed="slow" if score < 50 else "normal",
                          weak_points=safe_json_dumps([{"name": k.name, "score": 40 + (idx_seed % 30)}
                                                        for k in rng_kp[:5]]),
                          recommendation=f"建议优先补强薄弱知识点。{course.name}前测 {score} 分。")
    db.add(prof); db.flush()
    for k in rng_kp:
        ms = min(95, max(20, score + (idx_seed % 5) * 3 - k.difficulty * 2))
        db.add(KnowledgeMastery(student_id=student.id, course_id=course.id, kp_id=k.id,
                                mastery_score=ms, pre_score=ms,
                                status="mastered" if ms >= 80 else ("consolidated" if ms >= 60 else "weak")))
    # 后测（部分）
    if idx_seed % 2 == 0:
        post = min(98, score + 18 + (idx_seed % 8))
        db.add(PostTest(student_id=student.id, course_id=course.id,
                        question_ids=safe_json_dumps([q.id for q, _, _ in answers]),
                        total=len(answers), correct=int(post / 100 * len(answers)),
                        score=post, pre_score=score, improvement=round(post - score, 1),
                        finished_at=utc_now() - timedelta(days=1),
                        by_kp=safe_json_dumps([{"kp_id": k.id, "pre": score, "post": post,
                                                 "improvement": round(post - score, 1)}
                                                for k in rng_kp[:5]])))
        prof.post_score = post
        prof.stage = "post_test"


def _index_demo_file(db, course_id, uploader_id, rel_path):
    """预置演示课程资料文件，解析为 SQLite 检索片段。"""
    from pathlib import Path
    from app.core.config import BASE_DIR, settings
    from app.rag.parser import parse_file
    from app.rag.chunker import chunk_pages

    src = BASE_DIR / "demo_data" / rel_path
    if not src.exists():
        return
    # 复制到 uploads
    upload_dir = Path(settings.UPLOAD_DIR) / f"course_{course_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dst = upload_dir / src.name
    dst.write_bytes(src.read_bytes())

    cf = CourseFile(course_id=course_id, uploader_id=uploader_id, filename=src.name,
                    stored_path=str(dst), file_type="md", size=src.stat().st_size,
                    parse_status="parsed", indexed=True,
                    parse_summary=f"预置演示资料，已解析并建立本地检索片段。")
    db.add(cf); db.flush()

    pages = parse_file(dst)
    chunks_raw = chunk_pages(pages)
    chunk_objs = []
    for i, c in enumerate(chunks_raw):
        obj = DocumentChunk(course_id=course_id, file_id=cf.id, chunk_index=i,
                            text=c["text"], page=c.get("page", 1), source_name=src.name,
                            tokens=len(c["text"]))
        db.add(obj); chunk_objs.append(obj)
    db.commit()


def _seed_resources(db, course_objs, course_kp_maps):
    """Generate source-backed local demo resources and calculate their scores."""
    from app.services.builtin_generator import builtin
    from app.rag.retriever import retrieve, format_citations
    from app.services.quality_service import score_resource
    for cfg in COURSES_CONFIG:
        c = course_objs[cfg["name"]]
        kp_map = course_kp_maps[cfg["name"]]
        for topic_name in cfg["demo_topics"]:
            kp = kp_map.get(topic_name)
            if not kp:
                continue
            cites = format_citations(retrieve(db, c.id, topic_name, top_k=4))
            context = "\n".join(item["snippet"] for item in cites)
            content = builtin.chat(
                f"课程名称：{c.name}\n知识点：{topic_name}\n<course_context>{context}</course_context>"
            )
            r = GeneratedResource(course_id=c.id, kp_id=kp.id, rtype="lecture",
                                  title=f"{topic_name} · 讲义", content=content,
                                  citations=safe_json_dumps(cites), quality_score=0,
                                  review_status="published", published=True, agent_run_id=0)
            db.add(r)
            db.flush()
            score_resource(db, r, list(kp_map.values()), cites, c.id)
        # 每门课加思维导图、练习与 PPT
        first_topic = cfg["demo_topics"][0]
        first_kp = kp_map[first_topic]
        cites = format_citations(retrieve(db, c.id, first_topic, top_k=4))
        context = "\n".join(item["snippet"] for item in cites)
        mm = GeneratedResource(course_id=c.id, rtype="mindmap", title=f"{cfg['name']} 知识图谱",
                               content=builtin.chat(f"课程名称：{c.name}\n请生成思维导图\n<course_context>{context}</course_context>"),
                               citations=safe_json_dumps(cites), quality_score=0,
                               review_status="published", published=True)
        ex = GeneratedResource(course_id=c.id, kp_id=first_kp.id, rtype="exercise", title=f"{first_topic} · 练习题",
                               content=builtin.chat(f"课程名称：{c.name}\n知识点：{first_topic}\n请生成练习题\n<course_context>{context}</course_context>"),
                               citations=safe_json_dumps(cites), quality_score=0,
                               review_status="published", published=True)
        ppt = GeneratedResource(course_id=c.id, kp_id=first_kp.id, rtype="ppt", title=f"{first_topic} · PPT大纲",
                                content=builtin.chat(f"课程名称：{c.name}\n知识点：{first_topic}\n请生成PPT大纲\n<course_context>{context}</course_context>"),
                                citations=safe_json_dumps(cites), quality_score=0,
                                review_status="published", published=True)
        for r in (mm, ex, ppt):
            db.add(r)
            db.flush()
            score_resource(db, r, list(kp_map.values()), cites, c.id)
        db.commit()


# ---------- helper ----------

def _ensure_admin(db) -> User:
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        if admin.role != "admin":
            admin.role = "admin"
        admin.is_active = True
        db.commit()
        return admin
    admin = User(username="admin", email="admin@edu.cn", hashed_password=hash_password("123456"),
                 role="admin", full_name="系统管理员", is_active=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin

def _user(db, username, email, full_name, role, remark="", student_no="") -> User:
    u = db.query(User).filter(User.username == username).first()
    if u:
        return u
    _pwd = "123456"
    u = User(username=username, email=email, hashed_password=hash_password(_pwd),
             role=role, full_name=full_name, student_no=student_no, is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _course(db, name, code, teacher_id, desc, tags) -> Course:
    c = db.query(Course).filter(Course.name == name).first()
    if c:
        return c
    c = Course(name=name, code=code, description=desc, teacher_id=teacher_id, tags=tags, status="active")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _add_single(db, course_id, kp_id, kp_name, diff, domain):
    q = Question(course_id=course_id, kp_id=kp_id, qtype="single",
                 stem=f"关于「{kp_name}」，下列说法正确的是？",
                 answer="A",
                 analysis=f"{kp_name} 是{domain}课程的核心概念，相关要点已在讲义中阐述。",
                 difficulty=diff, tags=kp_name, source="seed")
    db.add(q); db.flush()
    db.add(QuestionOption(question_id=q.id, key="A", content=f"{kp_name}是{domain}的重要核心概念", is_correct=True, order_index=0))
    db.add(QuestionOption(question_id=q.id, key="B", content=f"{kp_name}与{domain}无关", is_correct=False, order_index=1))
    db.add(QuestionOption(question_id=q.id, key="C", content=f"{kp_name}仅用于其他领域", is_correct=False, order_index=2))
    db.add(QuestionOption(question_id=q.id, key="D", content=f"{kp_name}已经过时不再重要", is_correct=False, order_index=3))


def _add_judge(db, course_id, kp_id, kp_name, diff, domain):
    q = Question(course_id=course_id, kp_id=kp_id, qtype="judge",
                 stem=f"判断：{kp_name}是{domain}学习中必须掌握的核心知识。",
                 answer="正确", analysis=f"{kp_name}是{domain}的核心考点。",
                 difficulty=max(1, diff - 1), tags=kp_name, source="seed")
    db.add(q)


def _wrong_of(ans: str) -> str:
    if ans in ("A", "B", "C", "D"):
        return {"A": "B", "B": "C", "C": "D", "D": "A"}.get(ans, "B")
    if ans == "正确":
        return "错误"
    if ans == "错误":
        return "正确"
    return ans + "_x"


def _seed_agent_logs(db, course_id, student_id, trace_suffix=""):
    """Create one labeled offline trace from persisted demo data.

    Values are derived from the freshly seeded database. No synthetic latency,
    token count, model-call success, or learning experiment result is invented.
    """
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    relations = db.query(KnowledgeRelation).filter(KnowledgeRelation.course_id == course_id).count()
    chunks = db.query(DocumentChunk).filter(DocumentChunk.course_id == course_id).all()
    resources = db.query(GeneratedResource).filter(GeneratedResource.course_id == course_id).all()
    profile = db.query(StudentProfile).filter(
        StudentProfile.course_id == course_id,
        StudentProfile.student_id == student_id,
    ).first()
    path = db.query(LearningPath).filter(
        LearningPath.course_id == course_id,
        LearningPath.student_id == student_id,
    ).first()
    weak_count = len(json.loads(profile.weak_points or "[]")) if profile else 0
    avg_quality = round(sum(item.quality_score or 0 for item in resources) / max(1, len(resources)), 1)

    def resource_of(rtype: str):
        return next((item for item in resources if item.rtype == rtype), None)

    def citations_of(resource) -> int:
        if not resource:
            return 0
        try:
            return len(json.loads(resource.citations or "[]"))
        except (TypeError, json.JSONDecodeError):
            return 0

    lecture = resource_of("lecture")
    mindmap = resource_of("mindmap")
    exercise = resource_of("exercise")
    multimodal = [item for item in resources if item.rtype in {"ppt", "video", "experiment"}]

    trace = f"trace_seed_demo_001{trace_suffix}"
    run = AgentRun(
        trace_id=trace,
        course_id=course_id,
        student_id=student_id,
        workflow="full_pipeline",
        status="success",
        started_at=utc_now() - timedelta(minutes=10),
        finished_at=utc_now() - timedelta(minutes=10),
        duration_ms=0,
        progress=1.0,
        input_summary=safe_json_dumps({
            "course_id": course_id,
            "student_id": student_id,
            "demo_data": True,
        }),
        output_summary=safe_json_dumps({
            "demo_data": True,
            "note": "预置离线演示记录，不代表现场模型调用或性能测试",
            "lecture": {"quality": round(lecture.quality_score, 1) if lecture else 0},
            "exercise": {"questions": 4 if exercise else 0},
        }),
    )
    db.add(run)
    db.flush()
    agents = [
        ("CourseParserAgent", {"course_id": course_id}, {
            "pages": max([chunk.page for chunk in chunks] or [0]),
            "chunks": len(chunks),
            "points": len(kps),
        }),
        ("KnowledgeGraphAgent", {"course_id": course_id}, {
            "nodes": len(kps),
            "edges": relations,
        }),
        ("DiagnosisAgent", {"student_id": student_id}, {
            "pre_score": round(profile.pre_score, 1) if profile else 0,
            "weak_count": weak_count,
        }),
        ("PlannerAgent", {"student_id": student_id}, {
            "nodes": len(json.loads(path.nodes or "[]")) if path else 0,
            "total_minutes": path.total_minutes if path else 0,
        }),
        ("LectureAgent", {"kp": "核心概念"}, {
            "resource_id": lecture.id if lecture else None,
            "quality": round(lecture.quality_score, 1) if lecture else 0,
            "citations": citations_of(lecture),
        }),
        ("MindMapAgent", {}, {
            "resource_id": mindmap.id if mindmap else None,
            "nodes": len(kps),
            "edges": relations,
            "citations": citations_of(mindmap),
        }),
        ("ExerciseAgent", {"kp": "核心概念"}, {
            "questions": 4 if exercise else 0,
            "quality": round(exercise.quality_score, 1) if exercise else 0,
            "citations": citations_of(exercise),
        }),
        ("MultimodalResourceAgent", {"rtypes": ["ppt", "video", "experiment"]}, {
            "resource_ids": [item.id for item in multimodal],
            "rtypes": [item.rtype for item in multimodal],
            "citations": sum(citations_of(item) for item in multimodal),
        }),
        ("QualityCheckAgent", {}, {"checked": len(resources), "avg_score": avg_quality}),
        ("TeacherReviewAgent", {}, {"reviewed": len(resources), "suggestions": len(resources)}),
    ]
    from app.agents.base import AGENT_ROLES
    for i, (name, inp, outp) in enumerate(agents, 1):
        db.add(AgentLog(
            run_id=run.id,
            trace_id=trace,
            agent=name,
            step=i,
            status="success",
            input_summary=safe_json_dumps(inp),
            output_summary=safe_json_dumps({**outp, "demo_data": True}),
            duration_ms=0,
            role_description=AGENT_ROLES.get(name, ""),
            model_provider="mock",
            model_name="local-course-engine",
            citation_count=int(outp.get("citations") or 0),
            quality_score=float(outp.get("quality") or outp.get("avg_score") or 0),
            retry_count=0,
        ))


def _ensure_demo_agent_run(db) -> None:
    """Backfill one labeled offline trace into older seed databases only."""
    if db.query(AgentRun).first():
        return
    course = db.query(Course).filter(Course.status == "active").order_by(Course.id).first()
    if not course:
        return
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course.id
    ).order_by(CourseEnrollment.id).first()
    if not enrollment:
        return
    _seed_agent_logs(db, course.id, enrollment.student_id)
    db.commit()


if __name__ == "__main__":
    ensure_seed()
    print("seed done")
