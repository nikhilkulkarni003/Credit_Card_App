"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

type Bank = { id: string; name: string; code: string };

export function AddCardForm({ banks }: { banks: Bank[] }) {
  const router = useRouter();
  const [bankId, setBankId] = useState(banks[0]?.id ?? "");
  const [cardName, setCardName] = useState("");
  const [lastFour, setLastFour] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!/^\d{4}$/.test(lastFour)) {
      setError("Last 4 digits must be exactly 4 numbers.");
      return;
    }
    if (!bankId) {
      setError("Select a bank.");
      return;
    }

    setSubmitting(true);
    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    const { error: insertError } = await supabase.from("cards").insert({
      user_id: user!.id,
      bank_id: bankId,
      card_name: cardName,
      last_four_digits: lastFour,
      credit_limit: creditLimit ? Number(creditLimit) : null,
    });

    setSubmitting(false);
    if (insertError) {
      setError("Could not add card. It may already exist for this bank + last 4 digits.");
      return;
    }
    setCardName("");
    setLastFour("");
    setCreditLimit("");
    router.refresh();
  }

  if (!banks.length) {
    return (
      <p className="mt-4 text-sm text-zinc-500">
        No banks configured yet. Banks are added via the parser registry as support is built out.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-3">
      <select
        value={bankId}
        onChange={(e) => setBankId(e.target.value)}
        className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
      >
        {banks.map((bank) => (
          <option key={bank.id} value={bank.id}>
            {bank.name}
          </option>
        ))}
      </select>
      <input
        placeholder="Card nickname (e.g. HDFC Regalia)"
        value={cardName}
        onChange={(e) => setCardName(e.target.value)}
        required
        className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
      />
      <input
        placeholder="Last 4 digits"
        value={lastFour}
        onChange={(e) => setLastFour(e.target.value)}
        maxLength={4}
        required
        className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
      />
      <input
        placeholder="Credit limit (optional)"
        value={creditLimit}
        onChange={(e) => setCreditLimit(e.target.value)}
        type="number"
        className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
      >
        {submitting ? "Adding..." : "Add card"}
      </button>
    </form>
  );
}
