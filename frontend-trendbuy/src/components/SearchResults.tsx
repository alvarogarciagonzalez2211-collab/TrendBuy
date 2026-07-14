import type { ProductFamily } from "@/lib/types";
import { ProductFamilyCard } from "./ProductFamilyCard";

export function SearchResults({ families, query }: { families: ProductFamily[]; query: string }) {
  if (families.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No se han encontrado resultados para &quot;{query}&quot; en ninguna tienda.
      </p>
    );
  }

  return (
    // Rendered in the order the backend already sorted (discount % / historic
    // low first) - do not re-sort here, see CLAUDE.md rule 4.
    <div className="flex flex-col gap-4">
      {families.map((family) => (
        <ProductFamilyCard key={family.product_id} family={family} />
      ))}
    </div>
  );
}
