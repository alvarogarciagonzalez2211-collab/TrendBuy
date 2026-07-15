"use client";

import { INTERESTS, type Filters } from "@/lib/filters";

// The "what are you shopping for?" row: one tap filters everything below by
// purchase intent (tech, clothes, home...) without opening the detailed
// filter controls. Deliberately a single horizontal row that scrolls on
// mobile - it should read as a quick toggle, not another form.
export function InterestChips({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (next: Filters) => void;
}) {
  const select = (id: string) =>
    onChange({ ...filters, interest: filters.interest === id ? "all" : id, category: "all" });

  const chipClass = (selected: boolean) =>
    `inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium transition ${
      selected
        ? "border-zinc-900 bg-zinc-900 text-white shadow-sm dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
        : "border-zinc-300 bg-white text-zinc-600 hover:border-zinc-400 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:text-zinc-50"
    }`;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <button
        type="button"
        aria-pressed={filters.interest === "all"}
        onClick={() => onChange({ ...filters, interest: "all" })}
        className={chipClass(filters.interest === "all")}
      >
        Todo
      </button>
      {INTERESTS.map((interest) => (
        <button
          key={interest.id}
          type="button"
          aria-pressed={filters.interest === interest.id}
          onClick={() => select(interest.id)}
          className={chipClass(filters.interest === interest.id)}
        >
          <span aria-hidden>{interest.icon}</span>
          {interest.label}
        </button>
      ))}
    </div>
  );
}
