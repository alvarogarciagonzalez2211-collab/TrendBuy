// Affiliate disclosure is both a legal requirement (LSSI/consumer rules once
// affiliate links are live) and part of the product's "sin ruido" positioning:
// say plainly how the site sustains itself instead of hiding it.
export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-zinc-200 bg-white/60 dark:border-zinc-800 dark:bg-zinc-950/60">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-6 py-6 text-xs text-zinc-500 dark:text-zinc-400">
        <p>
          Algunos enlaces a tiendas son enlaces de afiliado: si compras a través de ellos, TrendBuy puede recibir
          una pequeña comisión de la tienda, <span className="font-medium">sin ningún coste extra para ti</span>.
          Es lo que mantiene el servicio gratuito. Los precios y el orden de los resultados nunca dependen de esas
          comisiones.
        </p>
        <p className="text-zinc-400 dark:text-zinc-500">
          Los precios se obtienen automáticamente de cada tienda y pueden variar desde la última actualización —
          comprueba siempre el precio final en la tienda.
        </p>
      </div>
    </footer>
  );
}
