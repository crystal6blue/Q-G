# FastAPI + Ollama (Docker) Question Generator

This project runs:
- FastAPI backend in Docker
- Ollama in Docker

The backend calls Ollama to generate questions from your prompt.
Backend dependencies are managed with Poetry (`backend/pyproject.toml`).

## Run

From this folder:

```bash
docker compose up --build
```

It will:
- start Ollama at `http://localhost:11434`
- pull the model `qwen2.5:3b` (first run can take time)
- start the API at `http://localhost:8000`

## Generate questions

```bash
curl -X POST http://localhost:8000/questions ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Interview questions about FastAPI dependency injection\",\"question_count\":5,\"variant_count\":4}"
```

Response now contains:
- `question`: question text
- `variants`: answer options
- `correct_answer`: correct answer text (string)

## Basic prompt/answer

```bash
curl -X POST http://localhost:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Explain what FastAPI is in 2 sentences\"}"
```

## Notes

- To change the model, edit `docker-compose.yml` (`OLLAMA_MODEL`).
- If you want the raw model output in responses, set `INCLUDE_RAW=1` for the `api` service.

