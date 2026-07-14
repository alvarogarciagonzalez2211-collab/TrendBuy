import { useState } from "react";
import { getProductAnalysis } from "./api";
import type { ProductAnalysis } from "./types";

// Shared by ProductFamilyCard and DealCard: both expand-on-click into the same
// price-history chart, and both need the exact same fetch/cache/error dance -
// fetches at most once per product per page load, kept in state rather than
// re-fetched on every expand/collapse toggle.
export function useProductAnalysis(productId: number) {
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [analysis, setAnalysis] = useState<ProductAnalysis | null>(null);

  async function toggle() {
    const next = !expanded;
    setExpanded(next);

    if (next && analysis === null && status !== "loading") {
      setStatus("loading");
      try {
        const data = await getProductAnalysis(productId);
        setAnalysis(data);
        setStatus("idle");
      } catch {
        setStatus("error");
      }
    }
  }

  return { expanded, status, analysis, toggle };
}
