"""Deterministic merchant -> category-name mapping (Stage 2, before AI fallback)."""

from __future__ import annotations

import re

# Ordered: more specific patterns first. Matched against the normalized merchant name.
DETERMINISTIC_RULES: list[tuple[str, str]] = [
    (r"\buber\b", "Cab"),
    (r"\bola\b", "Cab"),
    (r"\birctc\b", "Trains"),
    (r"\bbookmyshow\b", "Movies"),
    (r"\bnetflix\b", "OTT"),
    (r"\bhotstar\b|\bprime\s*video\b|\bsony\s*liv\b", "OTT"),
    (r"\bswiggy\b", "Food Delivery"),
    (r"\bzomato\b", "Food Delivery"),
    (r"\bbigbasket\b|\bblinkit\b|\bzepto\b|\bgrofers\b", "Groceries"),
    (r"\bamazon\b", "Online Shopping"),
    (r"\bflipkart\b|\bmyntra\b", "Online Shopping"),
    (r"\bmakemytrip\b|\bgoibibo\b|\byatra\b|\bindigo\b|\bair\s*india\b|\bvistara\b", "Flights"),
    (r"\boyo\b|\btaj\b\s*hotel|\bmarriott\b", "Hotels"),
    (r"\bpetrol|\bfuel|\bhpcl\b|\bbpcl\b|\biocl\b", "Fuel"),
    (r"\bapollo\s*pharmacy\b|\bpharmeasy\b|\bnetmeds\b", "Pharmacy"),
    (r"\bjio\b|\bairtel\b|\bvodafone\b|\bvi\b", "Mobile"),
    (r"\bgoogle\s*play\b|\bmicrosoft\b|\baws\b|\bgithub\b|\bopenai\b|\banthropic\b", "Software"),
]

_COMPILED_RULES = [(re.compile(pattern, re.IGNORECASE), category) for pattern, category in DETERMINISTIC_RULES]


def match_deterministic_rule(normalized_merchant: str) -> str | None:
    for pattern, category in _COMPILED_RULES:
        if pattern.search(normalized_merchant):
            return category
    return None
