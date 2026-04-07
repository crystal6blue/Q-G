from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateQuestionsRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Seed prompt / topic / context")
    question_count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    variant_count: int = Field(default=4, ge=2, le=10, description="Number of answer variants per question")


class QuestionItem(BaseModel):
    question: str
    variants: list[str]
    correct_answer: str = Field(description="Correct answer text (must be one of variants).")


class GenerateQuestionsResponse(BaseModel):
    model: str
    questions: list[QuestionItem]
    raw: str | None = None


class AskPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Prompt for basic AI answer")


class AskPromptResponse(BaseModel):
    model: str
    answer: str
    raw: str | None = None

