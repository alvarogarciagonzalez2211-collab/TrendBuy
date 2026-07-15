"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthHeader } from "./AuthHeader";

const NAV_LINKS = [
  { href: "/", label: "Inicio" },
  { href: "/favoritos", label: "Favoritos" },
];

function NavLinks({ onNavigate, className = "" }: { onNavigate?: () => void; className?: string }) {
  const pathname = usePathname();

  return (
    <nav className={className}>
      {NAV_LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              active
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

// Desktop shows nav + auth inline; below `sm` both collapse into a single
// hamburger-triggered panel so a narrow phone screen never has to squeeze
// the logo, nav links and the login form/email into one row.
export function HeaderNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    // Closes the mobile panel on navigation (link clicks already do this via
    // onNavigate, but this also covers back/forward and programmatic nav).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOpen(false);
  }, [pathname]);

  return (
    <div className="flex items-center gap-2">
      <NavLinks className="hidden items-center gap-1 sm:flex" />
      <div className="hidden sm:block">
        <AuthHeader />
      </div>

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={open ? "Cerrar menu" : "Abrir menu"}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-zinc-600 transition hover:bg-zinc-100 sm:hidden dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
          {open ? (
            <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
          ) : (
            <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
          )}
        </svg>
      </button>

      {open && (
        <div className="absolute inset-x-0 top-full border-b border-zinc-200 bg-white px-6 py-4 shadow-lg sm:hidden dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex flex-col gap-4">
            <NavLinks onNavigate={() => setOpen(false)} className="flex flex-col gap-1" />
            <div className="border-t border-zinc-100 pt-4 dark:border-zinc-800">
              <AuthHeader />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
