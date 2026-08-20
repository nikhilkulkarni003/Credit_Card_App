import json

import httpx
import pytest

from src.categorization.gemini_categorizer import GeminiCategorizer, GeminiCategorizerError

ALLOWED = {"Shopping", "Clothing", "Food Delivery"}


def make_categorizer(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return GeminiCategorizer(api_key="fake-key", allowed_categories=ALLOWED, http_client=client)


def test_suggest_parses_valid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps({"category": "Clothing", "confidence": 87, "reason": "Retail clothing purchase"})}]}}
            ]
        }
        return httpx.Response(200, json=body)

    categorizer = make_categorizer(handler)
    category, confidence, reason = categorizer.suggest("ABC Retail", "ABC RETAIL PVT LTD PUNE", "2450.00")

    assert category == "Clothing"
    assert confidence == 87.0
    assert "clothing" in reason.lower()


def test_suggest_sends_only_merchant_description_amount_and_categories():
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload["body"] = json.loads(request.content)
        captured_payload["url"] = str(request.url)
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps({"category": "Shopping", "confidence": 70, "reason": "x"})}]}}]}
        return httpx.Response(200, json=body)

    categorizer = make_categorizer(handler)
    categorizer.suggest("Test Merchant", "TEST MERCHANT DESC", "100.00")

    prompt_text = captured_payload["body"]["contents"][0]["parts"][0]["text"]
    assert "Test Merchant" in prompt_text
    assert "TEST MERCHANT DESC" in prompt_text
    assert "100.00" in prompt_text
    # security-critical: no password/token/secret fields anywhere in the request
    serialized = json.dumps(captured_payload["body"]).lower()
    for forbidden in ("password", "token", "secret", "client_secret"):
        assert forbidden not in serialized
    # API key travels as a query param, not embedded in the JSON body
    assert "fake-key" not in json.dumps(captured_payload["body"])
    assert "key=fake-key" in captured_payload["url"]


def test_suggest_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    categorizer = make_categorizer(handler)
    with pytest.raises(GeminiCategorizerError):
        categorizer.suggest("Merchant", "DESC", "10.00")


def test_suggest_raises_on_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    categorizer = make_categorizer(handler)
    with pytest.raises(GeminiCategorizerError):
        categorizer.suggest("Merchant", "DESC", "10.00")


def test_error_message_never_leaks_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "invalid key"})

    categorizer = make_categorizer(handler)
    try:
        categorizer.suggest("Merchant", "DESC", "10.00")
        assert False, "expected GeminiCategorizerError"
    except GeminiCategorizerError as exc:
        assert "fake-key" not in str(exc)
