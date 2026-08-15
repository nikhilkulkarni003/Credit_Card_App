import { createClient } from "@/lib/supabase/server";

export default async function StatementsPage() {
  const supabase = await createClient();
  const { data: statements } = await supabase
    .from("statements")
    .select("id, statement_date, due_date, total_amount_due, payment_status, processing_status, reconciliation_status, cards(card_name)")
    .order("statement_date", { ascending: false })
    .returns<
      {
        id: string;
        statement_date: string | null;
        due_date: string | null;
        total_amount_due: number | null;
        payment_status: string;
        processing_status: string;
        reconciliation_status: string;
        cards: { card_name: string } | null;
      }[]
    >();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Statements</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Statements appear here once the local agent downloads and processes them from Gmail.
        </p>
      </div>

      {statements?.length ? (
        <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-left text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Card</th>
                <th className="px-4 py-3 font-medium">Statement Date</th>
                <th className="px-4 py-3 font-medium">Due Date</th>
                <th className="px-4 py-3 font-medium">Total Due</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Reconciliation</th>
              </tr>
            </thead>
            <tbody>
              {statements.map((s) => (
                <tr key={s.id} className="border-t border-zinc-100">
                  <td className="px-4 py-3">{s.cards?.card_name}</td>
                  <td className="px-4 py-3">{s.statement_date}</td>
                  <td className="px-4 py-3">{s.due_date}</td>
                  <td className="px-4 py-3">{s.total_amount_due}</td>
                  <td className="px-4 py-3">{s.payment_status}</td>
                  <td className="px-4 py-3">{s.reconciliation_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-600">
          No statements yet. Run the local agent (<code className="rounded bg-zinc-100 px-1 py-0.5">services/local-agent</code>)
          to connect Gmail and scan for statements.
        </div>
      )}
    </div>
  );
}
