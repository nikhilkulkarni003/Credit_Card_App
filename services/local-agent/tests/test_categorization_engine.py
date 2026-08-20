from src.categorization.engine import CategorizationEngine


class FakeRuleStore:
    def __init__(self):
        self._rules: dict[tuple[str, str], str] = {}

    def lookup(self, user_id, normalized_merchant):
        return self._rules.get((user_id, normalized_merchant))

    def learn(self, user_id, normalized_merchant, category_name):
        self._rules[(user_id, normalized_merchant)] = category_name


class FakeAi:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def suggest(self, merchant, description, amount):
        self.calls.append((merchant, description, amount))
        if self.raises:
            raise self.raises
        return self.response


ALLOWED = {"Food Delivery", "Cab", "Shopping", "Clothing"}


def build_engine(rule_store=None, ai=None, ai_enabled=True, threshold=80.0):
    return CategorizationEngine(
        rule_store=rule_store or FakeRuleStore(),
        ai_categorizer=ai,
        ai_enabled=ai_enabled,
        confidence_threshold=threshold,
        allowed_categories=ALLOWED,
    )


def test_stage1_learned_rule_wins_over_everything():
    store = FakeRuleStore()
    store.learn("u1", "Uber", "Shopping")  # deliberately "wrong" vs deterministic, to prove stage 1 wins
    ai = FakeAi(("Cab", 99, "ai reason"))
    engine = build_engine(rule_store=store, ai=ai)

    result = engine.categorize("u1", "Uber", "UBER TRIP", "320.00")

    assert result.category_name == "Shopping"
    assert result.source == "merchant_rule"
    assert ai.calls == []  # AI must not be called when a learned rule exists


def test_stage2_deterministic_rule_used_when_no_learned_rule():
    ai = FakeAi(("Shopping", 99, "should not be used"))
    engine = build_engine(ai=ai)

    result = engine.categorize("u1", "Uber", "UBER TRIP", "320.00")

    assert result.category_name == "Cab"
    assert result.source == "deterministic_rule"
    assert ai.calls == []


def test_stage3_ai_fallback_for_unknown_merchant_high_confidence():
    ai = FakeAi(("Clothing", 92.0, "Looks like a retail clothing purchase."))
    engine = build_engine(ai=ai, threshold=80.0)

    result = engine.categorize("u1", "ABC Retail Pvt Ltd", "ABC RETAIL PVT LTD PUNE", "2450.00")

    assert result.category_name == "Clothing"
    assert result.source == "ai"
    assert result.needs_review is False
    assert ai.calls == [("ABC Retail Pvt Ltd", "ABC RETAIL PVT LTD PUNE", "2450.00")]


def test_stage3_ai_low_confidence_flagged_for_review():
    ai = FakeAi(("Shopping", 55.0, "uncertain"))
    engine = build_engine(ai=ai, threshold=80.0)

    result = engine.categorize("u1", "Weird Merchant", "WEIRD MERCHANT XYZ", "999.00")

    assert result.needs_review is True
    assert result.source == "ai"


def test_ai_failure_falls_back_to_uncategorized_instead_of_crashing():
    ai = FakeAi(raises=RuntimeError("network error"))
    engine = build_engine(ai=ai)

    result = engine.categorize("u1", "Weird Merchant", "WEIRD MERCHANT XYZ", "999.00")

    assert result.source == "uncategorized"
    assert result.needs_review is True
    assert result.category_name is None


def test_ai_rejected_category_outside_allowed_list():
    ai = FakeAi(("Not A Real Category", 99.0, "hallucinated"))
    engine = build_engine(ai=ai)

    result = engine.categorize("u1", "Weird Merchant", "WEIRD MERCHANT XYZ", "999.00")

    assert result.category_name is None
    assert result.source == "uncategorized"
    assert result.needs_review is True


def test_no_ai_available_falls_back_to_uncategorized():
    engine = build_engine(ai=None, ai_enabled=False)

    result = engine.categorize("u1", "Weird Merchant", "WEIRD MERCHANT XYZ", "999.00")

    assert result.source == "uncategorized"
    assert result.needs_review is True


def test_manual_override_teaches_the_engine():
    store = FakeRuleStore()
    engine = build_engine(rule_store=store, ai=FakeAi(("Shopping", 72.0, "low-confidence guess")))

    first = engine.categorize("u1", "ABC Retail", "ABC RETAIL PVT LTD", "2450.00")
    assert first.source == "ai"
    assert first.needs_review is True  # 72 < 80 threshold

    # User reviews and overrides to "Clothing"
    engine.record_manual_override("u1", "ABC Retail", "Clothing")

    second = engine.categorize("u1", "ABC Retail", "ABC RETAIL PVT LTD", "2450.00")
    assert second.category_name == "Clothing"
    assert second.source == "merchant_rule"
