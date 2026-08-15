import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/cards", label: "Cards" },
  { href: "/dashboard/statements", label: "Statements" },
  { href: "/dashboard/transactions", label: "Transactions" },
  { href: "/dashboard/categories", label: "Categories" },
  { href: "/dashboard/reports", label: "Reports" },
  { href: "/dashboard/settings", label: "Settings" },
];

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen flex-1">
      <aside className="w-56 shrink-0 border-r border-zinc-200 bg-white px-4 py-6">
        <div className="mb-8 px-2 text-lg font-semibold tracking-tight text-zinc-900">
          Credit Card CFO
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-2 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 bg-zinc-50 px-8 py-6">{children}</main>
    </div>
  );
}
