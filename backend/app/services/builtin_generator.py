"""Course-grounded offline generator.

This is not presented as a real foundation model. It is a deterministic local
fallback that keeps the complete teaching workflow usable without a key. Its
content is derived from the topic and RAG snippets present in the prompt, so a
finance, literature or engineering course will not fall back to computer-science
vocabulary.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from collections.abc import Iterator


STOPWORDS = {
    "课程", "资料", "内容", "知识", "知识点", "学生", "学习", "要求", "生成", "输出",
    "相关", "进行", "一个", "一种", "以及", "通过", "可以", "需要", "主要", "当前",
    "系统", "部分", "问题", "结果", "分析", "建议", "目标", "核心", "片段", "参考",
}

POINT_PREFIXES = (
    "本课程把", "本课程", "本节把", "本节", "本文把", "本文", "该课程", "该知识点",
    "与", "和", "及", "并", "把", "将", "由", "为",
)

POINT_FRAGMENT_MARKERS = (
    "定义为", "用于", "需要", "必须", "能够", "可以", "形成", "完成", "执行", "记录",
    "保存", "保留", "支持", "依据", "结合", "之后", "后仍", "不能", "不允许",
)


def _field(prompt: str, *names: str, default: str = "课程核心主题") -> str:
    for name in names:
        patterns = [
            rf"{re.escape(name)}\s*[：:]\s*([^\n<>]+)",
            rf"<{re.escape(name)}>\s*(.*?)\s*</{re.escape(name)}>",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, re.S)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip(" 《》「」")
                if value:
                    return value[:80]
    title = re.search(r"《([^》]{2,80})》", prompt)
    return title.group(1).strip() if title else default


def _context(prompt: str) -> str:
    snippet_values = re.findall(r'"snippet"\s*:\s*"((?:\\.|[^"\\])*)"', prompt)
    if snippet_values:
        decoded = []
        for value in snippet_values:
            try:
                decoded.append(json.loads(f'"{value}"'))
            except Exception:
                decoded.append(value.replace("\\n", " "))
        joined = " ".join(decoded).strip()
        if joined:
            return joined[:8000]
    patterns = [
        r"<course_context>\s*(.*?)\s*</course_context>",
        r"课程资料(?:片段)?\s*[：:]\s*(.*?)(?:\n(?:学生画像|输出格式|任务目标|质量要求)[：:]|$)",
        r"参考资料\s*[：:]\s*(.*)$",
        r"资料\s*[：:]\s*(.*)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.S | re.I)
        if match:
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            if text:
                return text[:8000]
    return ""


def _sentences(text: str, limit: int = 8) -> list[str]:
    raw = re.split(r"(?<=[。！？；])|\n+|(?<=[.!?;])\s+", text or "")
    cleaned: list[str] = []
    for item in raw:
        line = re.sub(r"^[#>*\-\d.、\s]+", "", item).strip()
        line = re.sub(r"\s+", " ", line)
        if 12 <= len(line) <= 220 and line not in cleaned:
            cleaned.append(line)
        if len(cleaned) >= limit:
            break
    return cleaned


def _normalise_point_candidate(value: str) -> str:
    value = re.sub(r"^[#>*\-\d.、一二三四五六七八九十\s]+", "", value or "")
    value = re.sub(r"\s+", " ", value).strip(" ：:，,。；;（）()《》「」『』\"'“”")
    for prefix in POINT_PREFIXES:
        if value.startswith(prefix) and len(value) > len(prefix) + 1:
            value = value[len(prefix):].strip()
            break
    value = re.split(
        r"(?:必须|需要|能够|可以|应当|应该|由独立|由系统|用于|形成|完成|执行|记录|保存|保留|支持|后仍|不能|不允许)",
        value,
        maxsplit=1,
    )[0]
    return value.strip(" ：:，,。；;的了与和及并")


def _valid_keyword(value: str) -> bool:
    if not value or value in STOPWORDS or not (2 <= len(value) <= 18):
        return False
    if value.startswith(POINT_PREFIXES):
        return False
    if any(marker in value for marker in POINT_FRAGMENT_MARKERS):
        return False
    if value.endswith(("后", "时", "之后", "以后")):
        return False
    if re.fullmatch(r"(?:本|该|其|此|一次|一种|一条|多个|每个|当前|相关|主要).{0,5}", value):
        return False
    return True


def _keywords(text: str, limit: int = 12) -> list[str]:
    """Extract readable domain concepts without pretending to be a segmenter.

    The offline provider deliberately favours author supplied structure
    (quoted definitions, headings and enumerations). Splitting every ten
    Chinese characters produced sentence fragments such as ``本课程把`` and
    ``定义为一次可追溯资源``; those are not useful knowledge points.
    """
    source = text or ""
    ranked: list[str] = []

    def add(value: str) -> None:
        candidate = _normalise_point_candidate(value)
        if _valid_keyword(candidate) and candidate not in ranked:
            ranked.append(candidate)

    for value in re.findall(r"[“「『《\"]([^”」』》\"\n]{2,24})[”」』》\"]", source):
        add(value)

    # Preserve authored domain acronyms (RAG, BM25, SQL, etc.) before longer
    # enumerations consume the output limit.
    for value in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,24}", source):
        add(value)

    for value in re.findall(
        r"(?:^|\n)\s*(?:#{1,6}\s*|第[一二三四五六七八九十\d]+[章节篇]\s*)([^\n]{2,40})",
        source,
    ):
        add(re.sub(r"^[一二三四五六七八九十\d]+[、.．]\s*", "", value))

    for value in re.findall(
        r"([A-Za-z][A-Za-z0-9 _-]{1,30}|[一-龥]{2,18})\s*(?:是指|指的是|定义为)",
        source,
    ):
        add(value)

    for sentence in re.split(r"[。！？；;\n]+", source):
        if sentence.count("、") + sentence.count("，") + sentence.count(",") < 2:
            continue
        list_body = sentence.split("：", 1)[-1].split(":", 1)[-1]
        for value in re.split(r"、|，|,|以及|和|与", list_body):
            add(value)

    if len(ranked) < limit:
        counter: Counter[str] = Counter()
        for span in re.findall(r"[一-龥]{2,18}", source):
            for size in (4, 3, 2):
                if len(span) < size:
                    continue
                counter.update(span[index:index + size] for index in range(len(span) - size + 1))
        for value, count in counter.most_common():
            if count < 2:
                break
            add(value)
            if len(ranked) >= limit:
                break

    return ranked[:limit]


def _evidence(topic: str, prompt: str) -> tuple[list[str], list[str]]:
    context = _context(prompt)
    facts = _sentences(context, 8)
    if not facts:
        facts = [
            f"当前任务围绕“{topic}”展开，演示模式会保留完整结构，但不会补造课程资料中未出现的事实。",
            "教师上传并完成解析后，系统会用真实课程片段替换这段演示说明。",
        ]
    keys = _keywords(" ".join(facts), 10) or [topic]
    return facts, keys


class BuiltinGenerator:
    model = "local-course-engine"

    def chat(self, prompt: str, system: str = "") -> str:
        return self._generate(prompt, system)

    def stream(self, prompt: str, system: str = "") -> Iterator[str]:
        text = self._generate(prompt, system)
        for index in range(0, len(text), 24):
            yield text[index:index + 24]
            time.sleep(0.006)

    def _generate(self, prompt: str, system: str) -> str:
        lowered = prompt.lower()
        # Route by the trusted role marker before inspecting course evidence.
        # Evidence may legitimately contain words such as “教师审核” or
        # “质量校验”; keyword-first dispatch would then send an exercise prompt
        # to the wrong generator and produce invalid structured output.
        if "角色：课程解析智能体" in prompt:
            return self._course_parse(prompt)
        if "角色：质量校验智能体" in prompt:
            return self._quality(prompt)
        if "角色：教师审核智能体" in prompt:
            return self._review(prompt)
        if "角色：讲义生成智能体" in prompt:
            return self._lecture(prompt)
        if "角色：练习生成智能体" in prompt:
            return self._exercise(prompt)
        if "角色：思维导图智能体" in prompt:
            return self._mindmap(prompt)
        if "角色：知识图谱智能体" in prompt:
            return self._graph(prompt)
        if "角色：多模态资源智能体" in prompt:
            if "视频脚本" in prompt or re.search(r"资源类型\s*[：:]\s*video\b", lowered):
                return self._video(prompt)
            if re.search(r"资源类型\s*[：:]\s*ppt\b", lowered) or "演示文稿" in prompt or "ppt" in lowered:
                return self._ppt(prompt)
            if "实验任务" in prompt or "实践任务" in prompt or re.search(r"资源类型\s*[：:]\s*experiment\b", lowered):
                return self._practice(prompt)
            if "拓展阅读" in prompt or re.search(r"资源类型\s*[：:]\s*reading\b", lowered):
                return self._reading(prompt)

        # Compatibility fallbacks for older callers without an explicit role.
        if "chapters" in prompt and "points" in prompt:
            return self._course_parse(prompt)
        if "quality_check" in lowered:
            return self._quality(prompt)
        if "teacher_review" in lowered:
            return self._review(prompt)
        if "练习题" in prompt or '"questions"' in prompt:
            return self._exercise(prompt)
        if "错题复盘" in prompt:
            return self._wrong_review(prompt)
        if "补救资源" in prompt:
            return self._remedial(prompt)
        if "视频脚本" in prompt or re.search(r"资源类型\s*[：:]\s*video\b", lowered):
            return self._video(prompt)
        if re.search(r"资源类型\s*[：:]\s*ppt\b", lowered) or "演示文稿" in prompt or "ppt" in lowered:
            return self._ppt(prompt)
        if "实验任务" in prompt or "实践任务" in prompt or re.search(r"资源类型\s*[：:]\s*experiment\b", lowered):
            return self._practice(prompt)
        if "拓展阅读" in prompt or re.search(r"资源类型\s*[：:]\s*reading\b", lowered):
            return self._reading(prompt)
        if "思维导图" in prompt or "mindmap" in lowered:
            return self._mindmap(prompt)
        if "知识图谱" in prompt or "knowledge_graph" in lowered:
            return self._graph(prompt)
        if "生成学生画像" in prompt or "角色：学生诊断" in prompt or (
            "base_level" in prompt and "weak_points" in prompt and "recommendation" in prompt
        ):
            return self._profile(prompt)
        return self._lecture(prompt)

    def _course_parse(self, prompt: str) -> str:
        facts, keys = _evidence("课程资料", prompt)
        chapter_titles = []
        context = _context(prompt)
        for title in re.findall(r"(?:^|\n)\s*(?:第[一二三四五六七八九十\d]+[章节篇]|#+)\s*([^\n]{2,30})", context):
            cleaned = title.strip(" ：:")
            if cleaned and cleaned not in chapter_titles:
                chapter_titles.append(cleaned)
        if not chapter_titles:
            chapter_titles = ["课程导入与问题背景", "核心概念与方法", "应用场景与案例", "复习与综合实践"]
        points = []
        for index, key in enumerate(keys[:16]):
            points.append({
                "name": key,
                "description": next((fact for fact in facts if key in fact), facts[index % len(facts)]),
                "keywords": key,
                "difficulty": min(5, 2 + index // 5),
            })
        return json.dumps({
            "chapters": [{"title": title, "summary": facts[i % len(facts)][:100]} for i, title in enumerate(chapter_titles[:8])],
            "points": points,
        }, ensure_ascii=False, indent=2)

    def _lecture(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        course = _field(prompt, "课程名称", "课程", default="当前课程")
        facts, keys = _evidence(topic, prompt)
        fact_lines = "\n".join(f"- {fact}" for fact in facts[:5])
        key_lines = "\n".join(f"{i + 1}. **{key}**：结合证据片段理解其定义、作用与边界。" for i, key in enumerate(keys[:5]))
        return f"""# {topic} · 个性化学习讲义

> 所属课程：{course}。本讲义优先依据已检索课程资料生成；演示模式不会补造资料外的结论。

## 1. 学习目标

- 能用自己的话解释“{topic}”及其在课程中的位置。
- 能从材料中找出支撑结论的依据，并区分事实、观点与推论。
- 能完成一个由浅入深的应用任务，并识别常见误区。

## 2. 资料依据

{fact_lines}

## 3. 分层理解

### 基础层：先回答“是什么”

围绕“{topic}”，先建立概念边界：它解决什么问题、适用于什么情境、与相近概念有什么区别。

### 理解层：再回答“为什么”

{key_lines}

### 应用层：最后回答“怎么用”

阅读一个课程案例，标出情境、关键证据、判断过程和最终结论；任何结论都应能回指到资料依据。

## 4. 例题与示范解析

**例题**：请结合课程资料，说明“{topic}”的核心价值，并给出一条适用边界。

**解析思路**：先引用材料中的明确表述，再解释其含义，最后说明在何种条件下不能直接套用。答案应包含“证据—解释—边界”三个部分。

## 5. 易错点

- 只记结论，不说明结论来自哪一段课程资料。
- 把相关关系误当作因果关系，或忽略材料限定的适用条件。
- 使用绝对化措辞，导致表达超出课程资料能够支持的范围。

## 6. 学习建议

1. 用 3 句话复述概念：定义、作用、边界。
2. 为每条核心结论补一条材料依据。
3. 完成练习后，把错因归类为“概念、证据、推理、表达”之一。

## 7. 引用说明

引用来源与页码由系统右侧“课程依据”区域统一展示。
"""

    def _exercise(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        facts, keys = _evidence(topic, prompt)
        fact = facts[0]
        data = {
            "questions": [
                {
                    "qtype": "single",
                    "knowledge_point": topic,
                    "stem": f"依据课程资料，理解“{topic}”时最重要的做法是？",
                    "options": [
                        {"key": "A", "content": "先确认材料证据，再形成解释与结论", "is_correct": True},
                        {"key": "B", "content": "只记住一个结论，不考虑适用条件", "is_correct": False},
                        {"key": "C", "content": "用个人印象替代课程资料", "is_correct": False},
                        {"key": "D", "content": "忽略相近概念之间的差异", "is_correct": False},
                    ],
                    "answer": "A",
                    "analysis": f"课程片段强调：{fact} 因此答案需要体现证据约束。",
                    "wrong_reason": "若选其他项，通常是忽略证据、边界或概念区分。",
                    "difficulty": 2,
                },
                {
                    "qtype": "judge",
                    "knowledge_point": topic,
                    "stem": f"判断：学习“{topic}”时，结论应能够回指到课程资料中的依据。",
                    "options": [],
                    "answer": "正确",
                    "analysis": "这是 RAG 课程学习资源的基本要求，可降低无依据扩展。",
                    "wrong_reason": "把生成内容当作无需核验的最终结论。",
                    "difficulty": 2,
                },
                {
                    "qtype": "fill",
                    "knowledge_point": topic,
                    "stem": f"填空：围绕“{topic}”形成完整回答，通常需要“证据—解释—____”三个部分。",
                    "options": [],
                    "answer": "边界",
                    "analysis": "边界用于说明结论适用的条件，避免绝对化。",
                    "wrong_reason": "只关注定义，没有说明适用条件。",
                    "difficulty": 3,
                },
                {
                    "qtype": "short",
                    "knowledge_point": topic,
                    "stem": f"请结合一条课程资料中的明确证据，解释“{topic}”的含义、作用与适用边界。",
                    "options": [],
                    "answer": f"答案应先引用与“{topic}”直接相关的课程片段，再解释概念含义与作用，最后给出至少一条适用边界。",
                    "analysis": "按证据准确性、概念解释、边界完整性三个维度评分。",
                    "wrong_reason": "常见问题是无引用、概念混淆或缺少边界。",
                    "difficulty": 4,
                },
            ]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _mindmap(self, prompt: str) -> str:
        topic = _field(prompt, "课程名称", "知识点", "主题")
        _, keys = _evidence(topic, prompt)
        branches = keys[:8] or ["背景", "概念", "方法", "案例", "风险", "复习"]
        lines = ["mindmap", f"  root(({topic}))"] + [f"    {re.sub(r'[^一-龥A-Za-z0-9_-]', '', key) or '课程要点'}" for key in branches]
        return "```mermaid\n" + "\n".join(lines) + "\n```"

    def _graph(self, prompt: str) -> str:
        topic = _field(prompt, "课程名称", "课程", default="课程知识体系")
        _, keys = _evidence(topic, prompt)
        nodes = keys[:8] or ["问题背景", "核心概念", "分析方法", "应用案例", "质量评价"]
        lines = ["graph LR"]
        for index, node in enumerate(nodes):
            safe = node.replace('"', "")
            lines.append(f'  K{index}["{safe}"]')
        for index in range(len(nodes) - 1):
            lines.append(f"  K{index} --> K{index + 1}")
        return "```mermaid\n" + "\n".join(lines) + "\n```"

    def _ppt(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        facts, _ = _evidence(topic, prompt)
        evidence = facts[0][:90]
        return f"""# 《{topic}》教学演示文稿大纲

1. **封面**：主题、课程、适用对象
2. **学习任务**：本节课要解决的三个问题
3. **背景情境**：为什么需要理解 {topic}
4. **资料证据**：{evidence}
5. **核心概念**：定义、作用、适用边界
6. **案例推演**：情境—证据—判断—结论
7. **易错点**：概念混淆、证据不足、绝对化表达
8. **课堂练习**：一道判断题与一道开放题
9. **总结**：关键结论与课后任务
"""

    def _video(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        return f"""# 《{topic}》微课视频脚本

| 时间 | 画面 | 旁白 | 教学目的 |
|---|---|---|---|
| 00:00-00:15 | 真实学习情境与问题字幕 | 今天我们用一个具体问题理解“{topic}”。 | 建立动机 |
| 00:15-00:45 | 课程资料重点句高亮 | 先看材料明确告诉了我们什么，再区分事实与推论。 | 锁定证据 |
| 00:45-01:30 | 概念关系动画 | 从定义、作用和边界三个层次拆解核心概念。 | 分层讲解 |
| 01:30-02:10 | 案例推演流程 | 按“情境—证据—判断—结论”完成一次应用。 | 迁移应用 |
| 02:10-02:40 | 易错选项对比 | 注意无依据扩展、概念混淆和绝对化表达。 | 纠正常错 |
| 02:40-03:00 | 三问自测 | 你能否解释概念、指出证据并说明边界？ | 学习检测 |
"""

    def _practice(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        return f"""# {topic} · 综合实践任务

## 任务目标
围绕真实材料完成一次“证据提取—概念解释—方案表达—同伴复核”。

## 交付物
1. 一页证据表：原文、页码、对应结论。
2. 一张概念关系图：至少 5 个节点、4 条关系。
3. 一份 600 字分析：说明 {topic} 的价值与适用边界。
4. 一份复核记录：列出两处可能的误解并给出修订。

## 验收标准
- 证据可追溯；概念使用准确；结论不过度扩展；表达结构清晰。
"""

    def _reading(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        return f"""# {topic} · 拓展阅读任务单

1. 先精读教师上传资料中与“{topic}”直接相关的章节。
2. 建立术语表：术语、定义、出处、相近概念。
3. 选择一份公开权威资料，与课程材料比较观点和适用范围。
4. 写 300 字阅读札记：新认识、仍有疑问、可应用场景。

> 演示模式不虚构书目与链接；教师可在审核环节补充本课程指定文献。
"""

    def _wrong_review(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        return f"""# {topic} · 错题复盘

## 错因定位
- **概念层**：没有准确区分定义、作用与适用边界。
- **证据层**：答案没有引用课程材料，或引用与结论不匹配。
- **推理层**：从个别例子直接推出一般结论。
- **表达层**：使用绝对化措辞，遗漏限定条件。

## 四步复盘
1. 重写题目考查的知识点。
2. 找到一条能够支撑答案的课程原文。
3. 说明原答案错在概念、证据、推理还是表达。
4. 完成一道同知识点变式题并解释边界。
"""

    def _remedial(self, prompt: str) -> str:
        topic = _field(prompt, "知识点", "主题")
        return f"""# {topic} · 补救学习包

## 一句话框架
先说清“是什么”，再说明“为什么”，最后回答“在什么条件下适用”。

## 记忆卡
- 正面：{topic} 的定义是什么？
- 背面：用课程原文作依据，并补充一条适用边界。

## 15 分钟补救任务
1. 5 分钟：阅读引用片段并圈出关键词。
2. 5 分钟：用自己的话复述，禁止照抄。
3. 5 分钟：完成一道变式题并标注证据。

## 达标检查
- [ ] 能准确解释概念
- [ ] 能指出材料依据
- [ ] 能识别一个常见误区
- [ ] 能说明适用边界
"""

    def _profile(self, prompt: str) -> str:
        return json.dumps({
            "base_level": "basic",
            "pref_style": "理解与案例结合",
            "pref_format": "图解,案例,短练习",
            "learning_speed": "normal",
            "weak_points": ["概念边界", "证据引用", "迁移应用"],
            "recommendation": "先补齐核心概念，再用课程证据完成案例练习；每次错题按概念、证据、推理、表达四类复盘。",
        }, ensure_ascii=False, indent=2)

    def _quality(self, prompt: str) -> str:
        def metric(name: str, default: float) -> float:
            match = re.search(rf'"{re.escape(name)}"\s*:\s*(-?\d+(?:\.\d+)?)', prompt)
            value = float(match.group(1)) if match else default
            return round(max(0.0, min(value, 100.0)), 1)

        # ``heuristic_score`` and the component values are produced by the
        # persisted rule-based QualityReport. Mirroring that evidence keeps
        # offline/demo mode deterministic without presenting a fabricated
        # fixed score as an independent model judgement.
        score = metric("heuristic_score", 0.0)
        coverage = metric("coverage", score)
        citation_hit = metric("citation_hit", 0.0)
        answer_consistency = metric("answer_consistency", score)
        difficulty_match = metric("difficulty_match", score)
        risk = metric("risk", 0.0)
        publishable = score >= 70 and risk == 0 and citation_hit >= 25
        risks = []
        suggestions = []
        if citation_hit < 50:
            risks.append("课程引用命中率不足，需教师核对证据")
            suggestions.append("补充与核心结论直接对应的课程引用")
        if coverage < 60:
            risks.append("知识点覆盖不足")
            suggestions.append("补齐目标知识点与必要的先修概念")
        if answer_consistency < 100:
            suggestions.append("复核答案、正确选项与解析是否一致")
        if risk > 0:
            risks.append("规则检查发现风险措辞")
            suggestions.append("删除绝对化表述并核对事实边界")
        return json.dumps({
            "score": score,
            "publishable": publishable,
            "checks": {
                "groundedness": citation_hit,
                "coverage": coverage,
                "answer_consistency": answer_consistency,
                "difficulty_match": difficulty_match,
                "citation_sufficiency": citation_hit,
            },
            "risks": risks,
            "suggestions": list(dict.fromkeys(suggestions)),
        }, ensure_ascii=False, indent=2)

    def _review(self, prompt: str) -> str:
        return json.dumps({
            "decision": "needs_human_review",
            "summary": "结构完整，可进入教师复核；发布前需核对课程引用与答案一致性。",
            "checklist": ["引用页码可追溯", "核心结论与资料一致", "难度适合目标学生", "无绝对化表述"],
        }, ensure_ascii=False, indent=2)


builtin = BuiltinGenerator()
