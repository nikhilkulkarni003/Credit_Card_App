"""
MerchantRuleStore backed by the real `merchant_rules` / `categories` tables.
Implements the Protocol defined in src/categorization/engine.py.
"""

from __future__ import annotations

from supabase import Client


class SupabaseMerchantRuleStore:
    def __init__(self, client: Client) -> None:
        self._client = client
        self._category_id_by_name: dict[str, str] = {}

    def lookup(self, user_id: str, normalized_merchant: str) -> str | None:
        response = (
            self._client.table("merchant_rules")
            .select("category_id, categories(name)")
            .eq("user_id", user_id)
            .eq("merchant_pattern", normalized_merchant)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        category = row.get("categories")
        return category["name"] if category else None

    def learn(self, user_id: str, normalized_merchant: str, category_name: str) -> None:
        category_id = self._get_category_id(user_id, category_name)
        if category_id is None:
            return  # unknown category name — do not silently create one
        self._client.table("merchant_rules").upsert(
            {
                "user_id": user_id,
                "merchant_pattern": normalized_merchant,
                "normalized_merchant": normalized_merchant,
                "category_id": category_id,
            },
            on_conflict="user_id,merchant_pattern",
        ).execute()

    def allowed_category_names(self, user_id: str) -> set[str]:
        response = (
            self._client.table("categories").select("name").eq("user_id", user_id).eq("active", True).execute()
        )
        return {row["name"] for row in response.data}

    def _get_category_id(self, user_id: str, category_name: str) -> str | None:
        if category_name in self._category_id_by_name:
            return self._category_id_by_name[category_name]
        response = (
            self._client.table("categories")
            .select("id")
            .eq("user_id", user_id)
            .eq("name", category_name)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        category_id = response.data[0]["id"]
        self._category_id_by_name[category_name] = category_id
        return category_id
