import { createClient } from "@/lib/supabase/server";

export default async function SettingsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const { count: cardCount } = await supabase.from("cards").select("id", { count: "exact", head: true });

  const rows = [
    { label: "Signed in as", value: user?.email ?? "—" },
    { label: "Cards configured", value: String(cardCount ?? 0) },
    { label: "Local Agent", value: "Not connected in this session (run services/local-agent separately)" },
    { label: "Statement Passwords", value: "Managed locally via the agent — never visible here" },
    { label: "AI Categorization", value: "Configured per-profile; disabled until a Gemini key is set locally" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Security &amp; Settings</h1>
        <p className="mt-1 text-sm text-zinc-500">
          This screen never displays passwords or OAuth tokens — see{" "}
          <code className="rounded bg-zinc-100 px-1 py-0.5">docs/security.md</code>.
        </p>
      </div>

      <div className="max-w-xl divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white shadow-sm">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between px-5 py-3 text-sm">
            <span className="text-zinc-500">{row.label}</span>
            <span className="font-medium text-zinc-900">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
