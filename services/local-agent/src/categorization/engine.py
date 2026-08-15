"""
Three-stage categorization engine.

  Stage 1 — exact learned merchant rule (user has categorized this exact
            merchant pattern before; matched via a MerchantRuleStore).
  Stage 2 — deterministic built-in rules (src/categorization/rules.py).
  Stage 3 — AI fallback (optional; only called for merchants that fell through
            stages 1 and 2, and only when enabled).

Every decision records `categorization_source` and, where applicable,
`categorization_confidence` / `categorization_reason`, so the audit trail
required by the product spec is always populated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.categorization.rules import match_deterministic_rule


@dataclass(frozen=True)
class CategorizationResult:
    category_name: str | None
    source: str  # 'merchant_rule' | 'deterministic_rule' | 'ai' | 'uncategorized'
    confidence: float | None
    reason: str
    needs_review: bool


class MerchantRuleStore(Protocol):
    def lookup(self, user_id: str, normalized_merchant: str) -> str | None:
        """Return a category name if a learned rule exists for this merchant, else None."""

    def learn(self, user_id: str, normalized_merchant: str, category_name: str) -> None:
        """Persist a merchant -> category mapping after a manual override or AI-confirmed pick."""


class AiCategorizer(Protocol):
    def suggest(self, merchant: str, description: str, amount: str) -> tuple[str, float, str]:
        """Return (category_name, confidence_0_to_100, reason). Must send only merchant/description/amount."""


class CategorizationEngine:
    def __init__(
        self,
        rule_store: MerchantRuleStore,
        ai_categorizer: AiCategorizer | None,
        ai_enabled: bool,
        confidence_threshold: float,
        allowed_categories: set[str],
    ) -> None:
        self._rule_store = rule_store
        self._ai = ai_categorizer
        self._ai_enabled = ai_enabled
        self._confidence_threshold = confidence_threshold
        self._allowed_categories = allowed_categories

    def categorize(self, user_id: str, normalized_merchant: str, description: str, amount: str) -> CategorizationResult:
        # Stage 1: learned merchant rule
        learned = self._rule_store.lookup(user_id, normalized_merchant)
        if learned:
            return CategorizationResult(
                category_name=learned,
                source="merchant_rule",
                confidence=100.0,
                reason=f"Matched learned rule for merchant '{normalized_merchant}'.",
                needs_review=False,
            )

        # Stage 2: deterministic built-in rules
        deterministic = match_deterministic_rule(normalized_merchant)
        if deterministic:
            return CategorizationResult(
                category_name=deterministic,
                source="deterministic_rule",
                confidence=95.0,
                reason=f"Matched built-in rule for merchant '{normalized_merchant}'.",
                needs_review=False,
            )

        # Stage 3: AI fallback (optional)
        if self._ai_enabled and self._ai is not None:
            category_name, confidence, reason = self._ai.suggest(normalized_merchant, description, amount)
            if category_name not in self._allowed_categories:
                return CategorizationResult(
                    category_name=None,
                    source="uncategorized",
                    confidence=confidence,
                    reason=f"AI suggested an unrecognized category '{category_name}'; rejected.",
                    needs_review=True,
                )
            needs_review = confidence < self._confidence_threshold
            return CategorizationResult(
                category_name=category_name,
                source="ai",
                confidence=confidence,
                reason=reason,
                needs_review=needs_review,
            )

        # No match, no AI available: leave uncategorized for manual review.
        return CategorizationResult(
            category_name=None,
            source="uncategorized",
            confidence=None,
            reason="No learned rule, no deterministic rule match, and AI categorization is unavailable/disabled.",
            needs_review=True,
        )

    def record_manual_override(self, user_id: str, normalized_merchant: str, category_name: str) -> None:
        """Called when the user accepts/changes a category — this is how the engine learns."""
        self._rule_store.learn(user_id, normalized_merchant, category_name)
