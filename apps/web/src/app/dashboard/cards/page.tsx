import { createClient } from "@/lib/supabase/server";
import { AddCardForm } from "./add-card-form";

export default async function CardsPage() {
  const supabase = await createClient();

  const [{ data: cards }, { data: banks }] = await Promise.all([
    supabase
      .from("cards")
      .select("id, card_name, last_four_digits, credit_limit, active, banks(name)")
      .order("created_at", { ascending: false })
      .returns<
        {
          id: string;
          card_name: string;
          last_four_digits: string;
          credit_limit: number | null;
          active: boolean;
          banks: { name: string } | null;
        }[]
      >(),
    supabase.from("banks").select("id, name, code").eq("active", true).order("name"),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Cards</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Add each credit card you want tracked. Statement passwords are configured
          separately in the local agent — never entered here.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(cards ?? []).map((card) => (
          <div key={card.id} className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-zinc-500">
              {card.banks?.name ?? "Unknown bank"}
            </p>
            <p className="mt-1 text-lg font-semibold text-zinc-900">{card.card_name}</p>
            <p className="text-sm text-zinc-500">•••• {card.last_four_digits}</p>
            {card.credit_limit && (
              <p className="mt-2 text-sm text-zinc-500">
                Limit: {new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(card.credit_limit)}
              </p>
            )}
          </div>
        ))}
        {!cards?.length && (
          <p className="text-sm text-zinc-500">No cards added yet.</p>
        )}
      </div>

      <div className="max-w-md rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-zinc-900">Add a card</h2>
        <AddCardForm banks={banks ?? []} />
      </div>
    </div>
  );
}
