"""Agent 基类：统一执行、计时、日志写入。"""
from __future__ import annotations
import time
import abc
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentLog, AgentRun
from app.services.llm_client import llm_client
from app.core.config import settings
from app.utils.redaction import redact_sensitive
from app.utils.time_util import safe_json_dumps


AGENT_ROLES = {
    "CourseParserAgent": "解析课程资料，完成文本抽取、分块、索引与知识点候选提取。",
    "KnowledgeGraphAgent": "根据课程知识点语义与顺序构建先修、关联和易混关系。",
    "DiagnosisAgent": "结合前测答题与学习目标识别能力水平和薄弱知识点。",
    "PlannerAgent": "依据画像、知识依赖和可用学习时间生成个性化学习路径。",
    "LectureAgent": "基于课程证据和学生画像生成分层讲义、复盘与补救资源。",
    "MindMapAgent": "把课程知识结构转化为可交互的思维导图与关系图。",
    "ExerciseAgent": "生成绑定知识点、难度、答案、解析和错因的结构化练习。",
    "MultimodalResourceAgent": "生成 PPT 大纲、视频脚本、实验任务和拓展阅读。",
    "QualityCheckAgent": "校验证据忠实性、覆盖度、一致性、难度和发布风险。",
    "TeacherReviewAgent": "汇总证据与质量结果，为教师提供可复核的审核建议。",
}


class BaseAgent(abc.ABC):
    name: str = "BaseAgent"
    purpose: str = "general"
    role_description: str = ""

    def __init__(self, db: Session, run: AgentRun, trace_id: str):
        self.db = db
        self.run = run
        self.trace_id = trace_id

    def run_agent(self, step: int, input_summary: Any) -> dict:
        """统一入口：执行 + 计时 + 落日志 + 更新进度。返回 output_summary。"""
        t0 = time.time()
        log = AgentLog(
            run_id=self.run.id,
            trace_id=self.trace_id,
            agent=self.name,
            step=step,
            status="success",
            input_summary=safe_json_dumps(input_summary),
            role_description=self.role_description or AGENT_ROLES.get(self.name, ""),
        )
        try:
            output = self.handle(input_summary)
            log.output_summary = safe_json_dumps(output)[:4000]
            log.duration_ms = int((time.time() - t0) * 1000)
            call = llm_client.call_info(self.trace_id)
            if call.get("trace_id") == self.trace_id:
                log.model_provider = str(call.get("provider") or "local")
                log.model_name = str(call.get("model") or "rule-engine")
                log.retry_count = int(call.get("retry_count") or 0)
                if call.get("fallback_used"):
                    log.status = "warning"
                    log.error = redact_sensitive(
                        call.get("error") or "真实模型调用失败，已使用本地结果",
                        secrets=(settings.DEEPSEEK_API_KEY, settings.JWT_SECRET),
                    )[:1000]
            else:
                log.model_provider = "local"
                log.model_name = "rule-and-retrieval-engine"
            log.citation_count = int(output.get("citations") or output.get("citation_count") or 0)
            score = output.get("quality") or output.get("avg_score") or output.get("score") or 0
            log.quality_score = float(score) if isinstance(score, (int, float)) else 0.0
            self.db.add(log)
            # 推进进度（按 workflow 动态决定总步数）
            total = 10 if self.run.workflow == "full_pipeline" else 1
            self.run.progress = min(1.0, round(step / total, 2))
            self.db.commit()
            return output
        except Exception as e:
            # A flush/commit failure leaves SQLAlchemy in a failed transaction.
            # Roll it back before writing the failure trace, otherwise the
            # original parse/generation error is masked by PendingRollbackError.
            self.db.rollback()
            failure_log = AgentLog(
                run_id=self.run.id,
                trace_id=self.trace_id,
                agent=self.name,
                step=step,
                status="failed",
                input_summary=safe_json_dumps(input_summary),
                output_summary="{}",
                duration_ms=int((time.time() - t0) * 1000),
                role_description=self.role_description or AGENT_ROLES.get(self.name, ""),
                model_provider="local",
                model_name="rule-and-retrieval-engine",
                retry_count=0,
                error=redact_sensitive(
                    e,
                    secrets=(settings.DEEPSEEK_API_KEY, settings.JWT_SECRET),
                )[:1000],
            )
            self.db.add(failure_log)
            self.db.commit()
            raise

    @abc.abstractmethod
    def handle(self, input_summary: Any) -> dict:
        ...
