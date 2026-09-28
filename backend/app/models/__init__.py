"""聚合所有 ORM 模型，便于 init_db 一次性建表。"""
from app.models.user import User  # noqa: F401
from app.models.course import Course, CourseChapter, CourseFile, CourseEnrollment  # noqa: F401
from app.models.knowledge import KnowledgePoint, KnowledgeRelation  # noqa: F401
from app.models.profile import StudentProfile, KnowledgeMastery  # noqa: F401
from app.models.test import PreTest, PostTest, TestAnswer, AssessmentAttempt  # noqa: F401
from app.models.question import Question, QuestionOption  # noqa: F401
from app.models.resource import GeneratedResource, ResourceReview  # noqa: F401
from app.models.learning import LearningPath, LearningRecord, WrongQuestion  # noqa: F401
from app.models.agent import AgentRun, AgentLog  # noqa: F401
from app.models.quality import QualityReport  # noqa: F401
from app.models.system import SystemConfig, LLMCallLog  # noqa: F401
from app.models.chunk import DocumentChunk  # noqa: F401

__all__ = [
    "User", "Course", "CourseChapter", "CourseFile", "CourseEnrollment",
    "KnowledgePoint", "KnowledgeRelation",
    "StudentProfile", "KnowledgeMastery",
    "PreTest", "PostTest", "TestAnswer", "AssessmentAttempt",
    "Question", "QuestionOption",
    "GeneratedResource", "ResourceReview",
    "LearningPath", "LearningRecord", "WrongQuestion",
    "AgentRun", "AgentLog",
    "QualityReport",
    "SystemConfig", "LLMCallLog",
    "DocumentChunk",
]
