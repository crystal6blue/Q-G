from __future__ import annotations

from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    difficult = "difficult"


class QuestionStyle(str, Enum):
    scientific = "scientific"
    humanistic = "humanistic"
    general = "general"


class SourceType(str, Enum):
    none = "none"
    url = "url"
    file = "file"


class GenerateQuestionsRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Seed prompt / topic / context")
    question_count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    variant_count: int = Field(default=4, ge=2, le=10, description="Number of answer variants per question")
    difficulty: DifficultyLevel = DifficultyLevel.medium
    question_style: QuestionStyle = QuestionStyle.general
    source_type: SourceType = SourceType.none
    source_url: str | None = None
    source_filename: str | None = None
    source_file_base64: str | None = None


class GenerateQuestionsFromPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Topic or context for question generation")
    question_count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    variant_count: int = Field(default=4, ge=2, le=10, description="Number of answer variants per question")
    difficulty: DifficultyLevel = DifficultyLevel.medium
    question_style: QuestionStyle = QuestionStyle.general


class GenerateQuestionsFromUrlRequest(BaseModel):
    prompt: str = Field(default="", description="Optional prompt/context. If empty, generates from URL content", min_length=0)
    url: str = Field(description="URL to fetch content from")
    question_count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    variant_count: int = Field(default=4, ge=2, le=10, description="Number of answer variants per question")
    difficulty: DifficultyLevel = DifficultyLevel.medium
    question_style: QuestionStyle = QuestionStyle.general


class GenerateQuestionsFromFileRequest(BaseModel):
    prompt: str = Field(default="", description="Optional prompt/context. If empty, generates from file content", min_length=0)
    filename: str = Field(description="Name of file (used to detect format: .pdf, .docx, .txt, .md)")
    file_base64: str = Field(description="File content as base64-encoded string")
    question_count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    variant_count: int = Field(default=4, ge=2, le=10, description="Number of answer variants per question")
    difficulty: DifficultyLevel = DifficultyLevel.medium
    question_style: QuestionStyle = QuestionStyle.general


class QuestionItem(BaseModel):
    question: str
    variants: list[str]
    correct_answer: str = Field(description="Correct answer text (must be one of variants).")
    explanation: str | None = Field(default=None, description="Why this answer is correct")
    hint: str | None = Field(default=None, description="Hint for answering")
    category: str | None = Field(default=None, description="Category/topic of question")
    confidence_score: float | None = Field(default=None, description="Model's confidence in this question (0-1)")


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


# Database Pydantic schemas

class QuestionInDB(BaseModel):
    id: int
    quiz_id: int
    question_text: str
    variants: list[str]
    correct_answer: str
    explanation: str | None
    hint: str | None
    category: str | None
    confidence_score: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class QuizCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    difficulty: DifficultyLevel
    question_style: QuestionStyle
    prompt: str
    question_count: int
    variant_count: int


class QuizInDB(BaseModel):
    id: int
    title: str
    description: str | None
    difficulty: str
    question_style: str
    prompt: str
    question_count: int
    variant_count: int
    model: str
    created_at: datetime
    questions: list[QuestionInDB]

    class Config:
        from_attributes = True


class SaveQuizRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    questions: list[QuestionItem]
    difficulty: DifficultyLevel
    question_style: QuestionStyle
    question_count: int
    variant_count: int
    prompt: str
    model: str


