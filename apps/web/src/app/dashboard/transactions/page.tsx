import { createClient } from "@/lib/supabase/server";

export default async function TransactionsPage() {
  const supabase = await createClient();
  const { data: transactions } = await supabase
    .from("transactions")
    .select("id, transaction_date, merchant_name, amount, categorization_source, categorization_confidence, manually_reviewed, categories(name)")
    .order("transaction_date", { ascending: false })
    .limit(100)
    .returns<
      {
        id: string;
        transaction_date: string;
        merchant_name: string;
        amount: number;
        categorization_source: string | null;
        categorization_confidence: number | null;
        manually_reviewed: boolean;
        categories: { name: string } | null;
      }[]
    >();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Transactions</h1>
        <p className="mt-1 text-sm text-zinc-500">Most recent 100 transactions across all cards.</p>
      </div>

      {transactions?.length ? (
        <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-left text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Merchant</th>
                <th className="px-4 py-3 font-medium">Amount</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id} className="border-t border-zinc-100">
                  <td className="px-4 py-3">{t.transaction_date}</td>
                  <td className="px-4 py-3">{t.merchant_name}</td>
                  <td className="px-4 py-3">{t.amount}</td>
                  <td className="px-4 py-3">{t.categories?.name ?? "Uncategorized"}</td>
                  <td className="px-4 py-3">{t.categorization_source ?? "—"}</td>
                  <td className="px-4 py-3">{t.categorization_confidence ? `${t.categorization_confidence}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-600">
          No transactions yet — they appear once a statement is processed by the local agent.
        </div>
      )}
    </div>
  );
}
