import { createClient } from "@/lib/supabase/server";

export default async function CategoriesPage() {
  const supabase = await createClient();
  const { data: categories } = await supabase
    .from("categories")
    .select("id, name, parent_id, system_default")
    .order("name");

  const topLevel = (categories ?? []).filter((c) => !c.parent_id);
  const childrenOf = (parentId: string) => (categories ?? []).filter((c) => c.parent_id === parentId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Categories</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Default categories are seeded automatically on signup. Custom categories can be added later.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {topLevel.map((parent) => (
          <div key={parent.id} className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="font-medium text-zinc-900">{parent.name}</p>
            <ul className="mt-2 space-y-1">
              {childrenOf(parent.id).map((child) => (
                <li key={child.id} className="text-sm text-zinc-500">
                  {child.name}
                </li>
              ))}
            </ul>
          </div>
        ))}
        {!topLevel.length && (
          <p className="text-sm text-zinc-500">
            No categories yet — they are created automatically when your account is provisioned.
          </p>
        )}
      </div>
    </div>
  );
}
