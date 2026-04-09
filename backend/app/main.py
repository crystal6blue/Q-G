from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.db_models import Quiz, Question
from app.models import (
    AskPromptRequest,
    AskPromptResponse,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    GenerateQuestionsFromPromptRequest,
    GenerateQuestionsFromUrlRequest,
    GenerateQuestionsFromFileRequest,
    SaveQuizRequest,
    QuizInDB,
)
from app.question_gen import ask_prompt, generate_questions

app = FastAPI(title="Question Generator API", version="1.0.0")


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/questions/prompt", response_model=GenerateQuestionsResponse)
async def questions_from_prompt(req: GenerateQuestionsFromPromptRequest) -> GenerateQuestionsResponse:
    try:
        qs, chosen_model, raw = await generate_questions(
            prompt=req.prompt,
            n=req.question_count,
            variant_count=req.variant_count,
            difficulty=req.difficulty.value,
            question_style=req.question_style.value,
            source_type="none",
            source_url=None,
            source_filename=None,
            source_file_base64=None,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    # Keep only valid structured questions.
    qs = [q for q in qs if q.get("question") and len(q.get("variants", [])) >= 2]
    if not qs:
        raise HTTPException(status_code=502, detail="No questions produced by model.")

    include_raw = os.getenv("INCLUDE_RAW", "0") == "1"
    return GenerateQuestionsResponse(model=chosen_model, questions=qs, raw=(raw if include_raw else None))


@app.post("/questions/from-url", response_model=GenerateQuestionsResponse)
async def questions_from_url(req: GenerateQuestionsFromUrlRequest) -> GenerateQuestionsResponse:
    # If prompt is empty, use a generic prompt
    prompt = req.prompt if req.prompt.strip() else "Generate comprehensive questions about the provided content"

    try:
        qs, chosen_model, raw = await generate_questions(
            prompt=prompt,
            n=req.question_count,
            variant_count=req.variant_count,
            difficulty=req.difficulty.value,
            question_style=req.question_style.value,
            source_type="url",
            source_url=req.url,
            source_filename=None,
            source_file_base64=None,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    # Keep only valid structured questions.
    qs = [q for q in qs if q.get("question") and len(q.get("variants", [])) >= 2]
    if not qs:
        raise HTTPException(status_code=502, detail="No questions produced by model.")

    include_raw = os.getenv("INCLUDE_RAW", "0") == "1"
    return GenerateQuestionsResponse(model=chosen_model, questions=qs, raw=(raw if include_raw else None))


@app.post("/questions/from-file", response_model=GenerateQuestionsResponse)
async def questions_from_file(req: GenerateQuestionsFromFileRequest) -> GenerateQuestionsResponse:
    # If prompt is empty, use a generic prompt
    prompt = req.prompt if req.prompt.strip() else "Generate comprehensive questions about the provided content"

    try:
        qs, chosen_model, raw = await generate_questions(
            prompt=prompt,
            n=req.question_count,
            variant_count=req.variant_count,
            difficulty=req.difficulty.value,
            question_style=req.question_style.value,
            source_type="file",
            source_url=None,
            source_filename=req.filename,
            source_file_base64=req.file_base64,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    # Keep only valid structured questions.
    qs = [q for q in qs if q.get("question") and len(q.get("variants", [])) >= 2]
    if not qs:
        raise HTTPException(status_code=502, detail="No questions produced by model.")

    include_raw = os.getenv("INCLUDE_RAW", "0") == "1"
    return GenerateQuestionsResponse(model=chosen_model, questions=qs, raw=(raw if include_raw else None))


@app.post("/ask", response_model=AskPromptResponse)
async def ask(req: AskPromptRequest) -> AskPromptResponse:
    try:
        answer, chosen_model, raw = await ask_prompt(
            prompt=req.prompt,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    if not answer:
        raise HTTPException(status_code=502, detail="No answer produced by model.")

    include_raw = os.getenv("INCLUDE_RAW", "0") == "1"
    return AskPromptResponse(model=chosen_model, answer=answer, raw=(raw if include_raw else None))


# ============================================================================
# Quiz Management Endpoints
# ============================================================================


@app.post("/quizzes/save")
async def save_quiz(req: SaveQuizRequest, db: Session = Depends(get_db)) -> dict:
    """Save generated quiz to database."""
    quiz = Quiz(
        title=req.title,
        description=req.description,
        difficulty=req.difficulty.value,
        question_style=req.question_style.value,
        prompt=req.prompt,
        question_count=req.question_count,
        variant_count=req.variant_count,
        model=req.model,
    )
    db.add(quiz)
    db.flush()  # Get the quiz ID

    # Add questions
    for q in req.questions:
        question = Question(
            quiz_id=quiz.id,
            question_text=q.question,
            variants=q.variants,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            hint=q.hint,
            category=q.category,
            confidence_score=q.confidence_score,
        )
        db.add(question)

    db.commit()
    db.refresh(quiz)

    return {
        "id": quiz.id,
        "title": quiz.title,
        "message": f"Quiz saved with {len(req.questions)} questions",
    }


@app.get("/quizzes/{quiz_id}", response_model=QuizInDB)
async def get_quiz(quiz_id: int, db: Session = Depends(get_db)) -> QuizInDB:
    """Retrieve a specific quiz by ID."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return QuizInDB.from_orm(quiz)


@app.get("/quizzes")
async def list_quizzes(
    skip: int = 0,
    limit: int = 20,
    difficulty: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """List all quizzes with optional filtering."""
    query = db.query(Quiz)

    if difficulty:
        query = query.filter(Quiz.difficulty == difficulty)

    total = query.count()
    quizzes = (
        query.order_by(Quiz.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "quizzes": [
            {
                "id": q.id,
                "title": q.title,
                "description": q.description,
                "difficulty": q.difficulty,
                "question_style": q.question_style,
                "question_count": q.question_count,
                "created_at": q.created_at.isoformat(),
            }
            for q in quizzes
        ],
    }


@app.delete("/quizzes/{quiz_id}")
async def delete_quiz(quiz_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete a quiz and its questions."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    db.delete(quiz)
    db.commit()

    return {"message": f"Quiz {quiz_id} deleted"}


@app.post("/questions/prompt/save")
async def questions_from_prompt_and_save(
    req: GenerateQuestionsFromPromptRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Generate questions from prompt and save to database."""
    try:
        qs, chosen_model, raw = await generate_questions(
            prompt=req.prompt,
            n=req.question_count,
            variant_count=req.variant_count,
            difficulty=req.difficulty.value,
            question_style=req.question_style.value,
            source_type="none",
            source_url=None,
            source_filename=None,
            source_file_base64=None,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    # Keep only valid structured questions.
    qs = [q for q in qs if q.get("question") and len(q.get("variants", [])) >= 2]
    if not qs:
        raise HTTPException(status_code=502, detail="No questions produced by model.")

    # Save to database
    quiz = Quiz(
        title=req.prompt[:255],  # Use prompt as title
        description=f"Generated quiz from prompt",
        difficulty=req.difficulty.value,
        question_style=req.question_style.value,
        prompt=req.prompt,
        question_count=len(qs),
        variant_count=req.variant_count,
        model=chosen_model,
    )
    db.add(quiz)
    db.flush()

    for q in qs:
        question = Question(
            quiz_id=quiz.id,
            question_text=q.get("question", ""),
            variants=q.get("variants", []),
            correct_answer=q.get("correct_answer", ""),
            explanation=q.get("explanation"),
            hint=q.get("hint"),
            category=q.get("category"),
            confidence_score=q.get("confidence_score"),
        )
        db.add(question)

    db.commit()
    db.refresh(quiz)

    return {
        "quiz_id": quiz.id,
        "message": f"Quiz saved with {len(qs)} questions",
        "model": chosen_model,
    }


