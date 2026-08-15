import { createClient } from "@/lib/supabase/server";

function formatInr(amount: number | null): string {
  if (amount === null) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount);
}

export default async function DashboardPage() {
  const supabase = await createClient();

  const { data: statements } = await supabase
    .from("statements")
    .select("total_amount_due, minimum_amount_due, due_date, payment_status, interest, gst")
    .order("due_date", { ascending: true });

  const { data: cards } = await supabase.from("cards").select("id, card_name, active").eq("active", true);

  const rows = statements ?? [];
  const totalOutstanding = rows
    .filter((s) => s.payment_status !== "paid")
    .reduce((sum, s) => sum + (s.total_amount_due ?? 0), 0);
  const totalMinDue = rows
    .filter((s) => s.payment_status !== "paid")
    .reduce((sum, s) => sum + (s.minimum_amount_due ?? 0), 0);
  const totalFees = rows.reduce((sum, s) => sum + (s.interest ?? 0) + (s.gst ?? 0), 0);

  const sevenDaysFromNow = new Date();
  sevenDaysFromNow.setDate(sevenDaysFromNow.getDate() + 7);
  const dueSoon = rows.filter(
    (s) =>
      s.payment_status !== "paid" &&
      s.due_date &&
      new Date(s.due_date) <= sevenDaysFromNow
  );

  const kpis = [
    { label: "Total Outstanding", value: formatInr(totalOutstanding) },
    { label: "Total Minimum Due", value: formatInr(totalMinDue) },
    { label: "Due in Next 7 Days", value: String(dueSoon.length) },
    { label: "Interest + GST (all time)", value: formatInr(totalFees) },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-500">Your credit-card finances at a glance.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-zinc-500">{kpi.label}</p>
            <p className="mt-2 text-2xl font-semibold text-zinc-900">{kpi.value}</p>
          </div>
        ))}
      </div>

      {!cards?.length && (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center">
          <p className="text-sm text-zinc-600">
            No cards yet.{" "}
            <a href="/dashboard/cards" className="font-medium text-zinc-900 underline">
              Add your first card
            </a>{" "}
            to get started, then run the local agent to scan Gmail for statements.
          </p>
        </div>
      )}
    </div>
  );
}
