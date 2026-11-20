"""AI service — communicates with Google Gemini for marketing advice."""

from typing import AsyncGenerator

import google.generativeai as genai

from ..config import get_settings

settings = get_settings()

genai.configure(api_key=settings.GEMINI_API_KEY)

_SYSTEM_PROMPT = """You are an expert AI Marketing Strategy Assistant. Help businesses with:

- Marketing strategy development and planning
- Campaign ideation and execution frameworks
- Social media strategy and content calendars
- SEO guidance and keyword strategy
- Business growth and customer acquisition
- Branding, positioning, and messaging
- Email marketing and lead nurturing
- Paid advertising strategy (Google, Meta, etc.)
- Market analysis and competitive insights
- Analytics and KPI frameworks

Provide actionable, concise advice tailored to the user's context. Use bullet points and
structure where helpful. Keep responses practical and results-focused."""


def _build_contents(message: str, history: list[dict]) -> list[dict]:
    """Convert chat history + current message into Gemini content format."""
    contents = []
    for entry in history[-10:]:
        contents.append({"role": "user", "parts": [{"text": entry["message"]}]})
        contents.append({"role": "model", "parts": [{"text": entry["response"]}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    return contents


def _get_model() -> genai.GenerativeModel:
    return genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=_SYSTEM_PROMPT,
    )


async def stream_ai_response(
    message: str, history: list[dict]
) -> AsyncGenerator[str, None]:
    """Yield AI response tokens as they arrive from Gemini (streaming)."""
    model = _get_model()
    contents = _build_contents(message, history)

    response = await model.generate_content_async(contents, stream=True)
    async for chunk in response:
        try:
            text = chunk.text
            if text:
                yield text
        except ValueError:
            # Chunk blocked by safety filters — skip silently
            continue
