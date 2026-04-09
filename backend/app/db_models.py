from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    difficulty = Column(String(50))  # easy, medium, difficult
    question_style = Column(String(50))  # scientific, humanistic, general
    prompt = Column(Text)
    question_count = Column(Integer)
    variant_count = Column(Integer)
    model = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_json = Column(JSON, nullable=True)  # Store extra metadata

    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), index=True)
    question_text = Column(Text)
    variants = Column(JSON)  # List of answer options
    correct_answer = Column(String(500))
    explanation = Column(Text, nullable=True)  # Why is this the correct answer
    hint = Column(Text, nullable=True)  # Hint for the learner
    category = Column(String(100), nullable=True)  # Topic/category
    confidence_score = Column(Float, nullable=True)  # Model's confidence (0-1)
    created_at = Column(DateTime, default=datetime.utcnow)

    quiz = relationship("Quiz", back_populates="questions")
