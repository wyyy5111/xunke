from __future__ import annotations
from typing import Literal, Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class OptionIn(BaseModel):
    key: str = Field(min_length=1, max_length=8)
    content: str = Field(min_length=1, max_length=5000)
    is_correct: bool = False
    order_index: int = Field(default=0, ge=0, le=99)


class QuestionCreate(BaseModel):
    course_id: int
    kp_id: Optional[int] = None
    qtype: Literal["single", "multiple", "judge", "fill", "short", "code", "experiment"] = "single"
    stem: str = Field(min_length=1, max_length=10_000)
    answer: str = Field(min_length=1, max_length=10_000)
    analysis: str = Field(default="", max_length=20_000)
    difficulty: int = Field(default=3, ge=1, le=5)
    tags: str = Field(default="", max_length=128)
    options: List[OptionIn] = Field(default_factory=list)
    source: Literal["manual"] = "manual"

    @model_validator(mode="after")
    def _validate_answer_contract(self):
        if self.qtype not in {"single", "multiple"}:
            if self.options:
                raise ValueError("非选择题不能提交选项")
            return self

        if not 2 <= len(self.options) <= 8:
            raise ValueError("选择题必须包含 2 到 8 个选项")
        keys = [option.key.strip().upper() for option in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError("选择题选项键不能重复")
        correct_keys = [
            option.key.strip().upper() for option in self.options if option.is_correct
        ]
        submitted = set(self.answer.strip().upper().replace(",", "").replace("，", ""))
        if self.qtype == "single" and len(correct_keys) != 1:
            raise ValueError("单选题必须且只能设置一个正确选项")
        if self.qtype == "multiple" and not correct_keys:
            raise ValueError("多选题至少设置一个正确选项")
        if submitted != set(correct_keys):
            raise ValueError("参考答案必须与正确选项一致")
        return self


class OptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    content: str
    is_correct: bool

class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    kp_id: Optional[int]
    qtype: str
    stem: str
    answer: str
    analysis: str
    difficulty: int
    tags: str
    source: str
    citations: Any
    options: List[OptionOut] = Field(default_factory=list)
