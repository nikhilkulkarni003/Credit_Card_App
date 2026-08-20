"""
Gemini AI fallback categorizer (Stage 3 of the categorization engine).

Called ONLY for transactions that fell through the learned-rule and
deterministic-rule stages — never for every transaction, and never with more
data than strictly needed to categorize a single line item.

What is sent to Gemini: normalized merchant name, original description,
amount, and the user's own category name list (needed so it picks from valid
options). That's it.
What is NEVER sent: statement password, OAuth tokens, other transactions on
the statement, card number, any personal identifier beyond what's already in
the merchant/description string itself (which the bank already printed).
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger("local_agent.categorization.gemini")

_ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_PROMPT_TEMPLATE = """You are categorizing ONE credit card transaction for a personal finance app.
Given the merchant name, description, and amount below, pick the single best category
from this exact list (respond with the exact string from the list):

{categories}

Merchant: {merchant}
Description: {description}
Amount: {amount}

Respond with JSON only: {{"category": "<one of the categories above>", "confidence": <0-100 integer>, "reason": "<one short sentence>"}}"""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "confidence": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["category", "confidence", "reason"],
}


class GeminiCategorizerError(Exception):
    """Raised on API failure. Message must never include the API key."""


class GeminiCategorizer:
    """Implements the AiCategorizer protocol from src/categorization/engine.py."""

    def __init__(
        self,
        api_key: str,
        allowed_categories: set[str],
        model: str = "gemini-3.6-flash",
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._allowed_categories = allowed_categories
        self._model = model
        self._timeout = timeout_seconds
        self._http_client = http_client

    def suggest(self, merchant: str, description: str, amount: str) -> tuple[str, float, str]:
        prompt = _PROMPT_TEMPLATE.format(
            categories="\n".join(sorted(self._allowed_categories)),
            merchant=merchant,
            description=description,
            amount=amount,
        )
        url = _ENDPOINT_TEMPLATE.format(model=self._model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
            },
        }

        try:
            poster = self._http_client.post if self._http_client else httpx.post
            response = poster(url, params={"key": self._api_key}, json=payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Gemini API call failed: %s", type(exc).__name__)
            raise GeminiCategorizerError("AI categorization unavailable.") from exc

        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            category = str(parsed["category"])
            confidence = float(parsed["confidence"])
            reason = str(parsed["reason"])
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            logger.warning("Could not parse Gemini response shape.")
            raise GeminiCategorizerError("AI categorization returned an unexpected response.") from exc

        return category, confidence, reason
