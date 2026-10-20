"""llm_client.py — Configurable LLM adapter (Gemini / OpenAI)."""

import json
import os
import re
from typing import Any
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()


def _clean_json_text(text: str) -> str:
    """Strip markdown code blocks if the model wrapped JSON output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_llm(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Send a prompt to the configured LLM and parse JSON response.

    Returns: parsed dictionary from JSON response.
    """
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER).lower()
    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt)
    elif provider == "openai":
        return _call_openai(system_prompt, user_prompt)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: '{provider}'. Must be 'gemini' or 'openai'.")


def _call_gemini(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call Google Gemini API."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    genai.configure(api_key=api_key, transport="rest")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )

    response = model.generate_content(
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    cleaned = _clean_json_text(response.text)
    return json.loads(cleaned)


def _call_openai(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call OpenAI API."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    content = response.choices[0].message.content or "{}"
    cleaned = _clean_json_text(content)
    return json.loads(cleaned)
