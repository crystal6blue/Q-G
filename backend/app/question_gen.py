from __future__ import annotations

import base64
import io
import json
import os
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader


def _get_env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v else default


def _extract_json_array(text: str) -> list[str] | None:
    """
    Best-effort: extract a JSON array of strings from arbitrary model output.
    """
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return None
    candidate = m.group(0)
    try:
        data = json.loads(candidate)
    except Exception:
        return None
    if isinstance(data, list) and all(isinstance(x, str) for x in data):
        return [q.strip() for q in data if q.strip()]
    return None


def _extract_json_object_array(text: str) -> list[dict[str, Any]] | None:
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return None
    candidate = m.group(0)
    try:
        data = json.loads(candidate)
    except Exception:
        return None
    if isinstance(data, list) and all(isinstance(x, dict) for x in data):
        return data
    return None


def _extract_items_from_any_json_shape(text: str) -> list[dict[str, Any]] | None:
    """
    Accept common model output shapes:
    - [ {..}, {..} ]
    - { "questions": [ {..}, ... ] }
    - { "question": "...", "variants": [...], "correct_answers": [...] }
    - Stringified JSON object inside text
    """
    direct_array = _extract_json_object_array(text)
    if direct_array is not None:
        return direct_array

    # Try first JSON object in output.
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None

    if isinstance(obj, dict):
        questions = obj.get("questions")
        if isinstance(questions, list) and all(isinstance(x, dict) for x in questions):
            return questions
        if {"question", "variants", "correct_answers"}.issubset(set(obj.keys())):
            return [obj]
    return None


def _fallback_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", s)
        if s:
            lines.append(s)
    return lines


async def _chat_with_ollama(
    *,
    user_prompt: str,
    system_prompt: str,
    model: str | None,
    temperature: float,
) -> tuple[str, str]:
    base_url = _get_env("OLLAMA_BASE_URL", "http://ollama:11434")
    chosen_model = model or _get_env("OLLAMA_MODEL", "qwen2.5:3b")
    timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)

    payload: dict[str, Any] = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": float(temperature)},
    }
    last_response: httpx.Response | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Try native Ollama chat API first.
        r = await client.post(f"{base_url}/api/chat", json=payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            raw = str((data.get("message") or {}).get("content") or data.get("response", "") or "")
            return raw, chosen_model
        last_response = r

        # Try older generate API.
        legacy_payload: dict[str, Any] = {
            "model": chosen_model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": float(temperature)},
        }
        r = await client.post(f"{base_url}/api/generate", json=legacy_payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            raw = str((data.get("message") or {}).get("content") or data.get("response", "") or "")
            return raw, chosen_model
        last_response = r

        # Try OpenAI-compatible endpoint exposed by some Ollama setups.
        v1_payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature),
        }
        r = await client.post(f"{base_url}/v1/chat/completions", json=v1_payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices") or []
            first = choices[0] if isinstance(choices, list) and choices else {}
            raw = str(((first.get("message") or {}).get("content")) or "")
            return raw, chosen_model
        last_response = r

        # Helpful error when model isn't ready yet.
        try:
            tags_resp = await client.get(f"{base_url}/api/tags")
            if tags_resp.status_code == 200:
                tags = tags_resp.json().get("models") or []
                available = [str(m.get("name")) for m in tags if isinstance(m, dict) and m.get("name")]
                if chosen_model not in available:
                    raise RuntimeError(
                        f"Model '{chosen_model}' is not available yet. "
                        f"Currently available: {available or 'none'}. "
                        "Wait for model pull to finish or use an available model."
                    )
        except RuntimeError:
            raise
        except Exception:
            pass

    if last_response is not None:
        last_response.raise_for_status()
    raw = ""
    return raw, chosen_model


async def generate_questions(
    *,
    prompt: str,
    n: int,
    variant_count: int,
    difficulty: str,
    question_style: str,
    source_type: str,
    source_url: str | None,

    source_filename: str | None,
    source_file_base64: str | None,
    model: str | None,
    temperature: float,
) -> tuple[list[dict[str, Any]], str, str]:
    async def build_source_context() -> str:
        if source_type == "none":
            return ""

        if source_type == "url":
            if not source_url:
                return ""
            timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(source_url, headers=headers)
                r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            return text[:8000]

        if source_type == "file":
            if not source_file_base64 or not source_filename:
                return ""

            data = base64.b64decode(source_file_base64)
            filename = source_filename.lower()
            if filename.endswith(".pdf"):
                reader = PdfReader(io.BytesIO(data))
                text = " ".join(page.extract_text() or "" for page in reader.pages)
                return text[:8000]
            if filename.endswith(".docx"):
                doc = Document(io.BytesIO(data))
                text = " ".join(p.text for p in doc.paragraphs)
                return text[:8000]
            if filename.endswith(".txt") or filename.endswith(".md"):
                return data.decode("utf-8", errors="ignore")[:8000]

        return ""

    source_context = await build_source_context()

    def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_local: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item.get("question"), str):
                q_text = item.get("question", "").strip()
                # Some models put full JSON object as a string into "question".
                if q_text.startswith("{") and q_text.endswith("}"):
                    try:
                        nested = json.loads(q_text)
                        if isinstance(nested, dict):
                            item = nested
                    except Exception:
                        pass

            question = str(item.get("question", "")).strip()
            raw_variants = item.get("variants")
            raw_correct = item.get("correct_answers")
            if not question or not isinstance(raw_variants, list):
                continue

            variants = [str(v).strip() for v in raw_variants if str(v).strip()]
            if len(variants) < 2:
                continue
            if len(variants) > variant_count:
                variants = variants[:variant_count]

            correct_answers: list[int] = []
            if isinstance(raw_correct, list):
                for idx in raw_correct:
                    if isinstance(idx, int) and 0 <= idx < len(variants):
                        correct_answers.append(idx)
                # If model used 1-based indexing (e.g. [1,2,3,4]), convert to 0-based.
                if not correct_answers and all(isinstance(i, int) and 1 <= i <= len(variants) for i in raw_correct):
                    correct_answers = [i - 1 for i in raw_correct]
            correct_answers = sorted(set(correct_answers))
            if not correct_answers:
                correct_answers = [0]
            elif len(correct_answers) >= len(variants):
                correct_answers = [correct_answers[0]]

            normalized_local.append(
                {
                    "question": question,
                    "variants": variants,
                    "correct_answer": variants[correct_answers[0]],
                }
            )
        return normalized_local

    normalized: list[dict[str, Any]] = []
    raw_chunks: list[str] = []

    for _ in range(3):
        remaining = n - len(normalized)
        if remaining <= 0:
            break

        system = (
            "You generate multiple-choice questions for a user.\n"
            f"Return ONLY valid JSON: an array of exactly {remaining} objects.\n"
            "Each object schema:\n"
            '{ "question": string, "variants": [string, ...], "correct_answers": [int, ...] }\n'
            "Rules:\n"
            f"- difficulty must be {difficulty}.\n"
            f"- wording style must be {question_style}.\n"
            f"- variants must contain exactly {variant_count} options.\n"
            "- correct_answers must contain exactly one valid 0-based index.\n"
            "- No markdown, no explanations."
        )
        user_prompt = f"Topic/context: {prompt}"
        if source_context:
            user_prompt += f"\nUse this source material:\n{source_context}"
        raw, chosen_model = await _chat_with_ollama(
            user_prompt=user_prompt,
            system_prompt=system,
            model=model,
            temperature=temperature,
        )
        raw_chunks.append(raw)

        items = _extract_json_object_array(raw)
        if items is None:
            items = _extract_items_from_any_json_shape(raw)
        if items is None:
            lines = _extract_json_array(raw) or _fallback_lines(raw)
            items = []
            for line in lines:
                q = line.strip()
                if not q:
                    continue
                items.append(
                    {
                        "question": q,
                        "variants": ["True", "False"],
                        "correct_answers": [0],
                    }
                )

        parsed = normalize_items(items)
        existing = {q["question"].strip().lower() for q in normalized}
        for q in parsed:
            key = q["question"].strip().lower()
            if key in existing:
                continue
            normalized.append(q)
            existing.add(key)
            if len(normalized) >= n:
                break

    if len(normalized) > n:
        normalized = normalized[:n]

    return normalized, chosen_model, "\n\n".join(raw_chunks)


async def ask_prompt(
    *,
    prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
) -> tuple[str, str, str]:
    raw, chosen_model = await _chat_with_ollama(
        user_prompt=prompt,
        system_prompt="You are a helpful AI assistant. Give a clear and concise answer.",
        model=model,
        temperature=temperature,
    )
    answer = raw.strip()
    return answer, chosen_model, raw

