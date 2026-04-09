# FastAPI + Ollama + PostgreSQL Question Generator

This project runs:
- FastAPI backend in Docker
- Ollama in Docker
- PostgreSQL database in Docker

The backend calls Ollama to generate questions from your prompt and stores them in PostgreSQL.
Backend dependencies are managed with Poetry (`backend/pyproject.toml`).

## Run

From this folder:

```bash
docker compose up --build
```

It will:
- start PostgreSQL at `localhost:5432` (credentials: quiz_user / quiz_password)
- start Ollama at `http://localhost:11434`
- pull the model `llama3.2` (first run can take time)
- start the API at `http://localhost:8000`

## Generate and Save Questions

### Generate from prompt (without saving)
```bash
curl -X POST http://localhost:8000/questions/prompt ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Interview questions about FastAPI\",\"question_count\":5,\"variant_count\":4}"
```

### Generate from prompt and save to database
```bash
curl -X POST http://localhost:8000/questions/prompt/save ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Interview questions about FastAPI\",\"question_count\":5,\"variant_count\":4,\"difficulty\":\"medium\",\"question_style\":\"general\"}"
```

Response:
```json
{
  "quiz_id": 1,
  "message": "Quiz saved with 5 questions",
  "model": "llama3.2"
}
```

## Quiz Management

### List all quizzes
```bash
curl http://localhost:8000/quizzes
```

Filtering by difficulty:
```bash
curl "http://localhost:8000/quizzes?difficulty=medium"
```

Pagination:
```bash
curl "http://localhost:8000/quizzes?skip=0&limit=10"
```

### Get specific quiz
```bash
curl http://localhost:8000/quizzes/1
```

### Save manual quiz
```bash
curl -X POST http://localhost:8000/quizzes/save ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"My Quiz\",\"difficulty\":\"medium\",\"question_style\":\"general\",\"prompt\":\"Topic: FastAPI\",\"question_count\":1,\"variant_count\":4,\"questions\":[{\"question\":\"What is FastAPI?\",\"variants\":[\"Web framework\",\"Database\",\"ORM\",\"CSS\"]}]}"
```

### Delete quiz
```bash
curl -X DELETE http://localhost:8000/quizzes/1
```

## Question Structure

Questions now have enhanced fields:
- `question`: The question text
- `variants`: List of answer options
- `correct_answer`: The correct answer text
- `explanation`: Why this answer is correct (new)
- `hint`: Hint for answering (new)
- `category`: Topic/category (new)
- `confidence_score`: Model's confidence 0-1 (new)

## Basic prompt/answer

```bash
curl -X POST http://localhost:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Explain what FastAPI is in 2 sentences\"}"
```

## Notes

- To change the model, edit `docker-compose.yml` (`OLLAMA_MODEL`).
- If you want the raw model output in responses, set `INCLUDE_RAW=1` for the `api` service.
- Database credentials can be changed in `docker-compose.yml`
- All quizzes are automatically timestamped and stored in PostgreSQL

