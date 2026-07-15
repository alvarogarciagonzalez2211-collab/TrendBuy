"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { getAuthConfig, GOOGLE_LOGIN_URL, requestLogin } from "@/lib/api";
import { useAuth } from "@/lib/AppProviders";

// Google's own multi-color "G" mark, as published in their sign-in button
// guidelines - not a generic icon, this exact set of paths/colors is what
// "Continuar con Google" buttons are expected to use.
function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <path
        fill="#4285F4"
        d="M17.64 9.2045c0-.6381-.0573-1.2518-.1636-1.8409H9v3.4814h4.8436c-.2086 1.125-.8427 2.0782-1.7959 2.7164v2.2581h2.9087c1.7018-1.5668 2.6836-3.8741 2.6836-6.615z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.4673-.806 5.9564-2.1805l-2.9087-2.2581c-.8059.54-1.8368.8591-3.0477.8591-2.3436 0-4.3282-1.5831-5.036-3.7104H.9573v2.3318C2.4382 15.9832 5.4818 18 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.964 10.71c-.18-.54-.2822-1.1168-.2822-1.71s.1023-1.17.2823-1.71V4.9582H.9573A8.9965 8.9965 0 000 9c0 1.4523.3477 2.8268.9573 4.0418L3.964 10.71z"
      />
      <path
        fill="#EA4335"
        d="M9 3.5795c1.3214 0 2.5077.4541 3.4405 1.346l2.5813-2.5814C13.4632.8918 11.426 0 9 0 5.4818 0 2.4382 2.0168.9573 4.9582L3.964 7.29C4.6718 5.1618 6.6564 3.5795 9 3.5795z"
      />
    </svg>
  );
}

function LoginForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [googleEnabled, setGoogleEnabled] = useState(false);

  // Only shown once confirmed configured server-side (services/google_auth.py)
  // - without this check, clicking the button on an install that never set
  // GOOGLE_CLIENT_ID/SECRET would full-page-navigate to a raw 503 error.
  useEffect(() => {
    let cancelled = false;
    getAuthConfig()
      .then((config) => {
        if (!cancelled) setGoogleEnabled(config.google_login_enabled);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;

    setStatus("sending");
    try {
      await requestLogin(trimmed);
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  if (status === "sent") {
    return (
      <div className="flex items-start gap-2 text-sm text-emerald-700 dark:text-emerald-300">
        <span className="text-base">✉️</span>
        <p>Revisa tu correo y pulsa el enlace para entrar. Caduca en 15 minutos.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Accede a TrendBuy</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">Elige cómo prefieres entrar, sin contraseña.</p>
      </div>

      {googleEnabled && (
        <>
          <a
            href={GOOGLE_LOGIN_URL}
            className="flex items-center justify-center gap-2 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            <GoogleIcon />
            Continuar con Google
          </a>
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-600">
            <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
            o con tu email
            <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
          </div>
        </>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          Correo electrónico
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="tu@email.com"
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
          />
        </label>
        <button
          type="submit"
          disabled={status === "sending"}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {status === "sending" ? "Enviando..." : "Enviar enlace de acceso"}
        </button>
        {status === "error" && (
          <span className="text-xs text-red-600 dark:text-red-400">
            No se pudo enviar el enlace. Inténtalo de nuevo.
          </span>
        )}
      </form>
    </div>
  );
}

function AccountPanel({ onAction }: { onAction?: () => void }) {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-sm font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
          {user.email.charAt(0).toUpperCase()}
        </span>
        <span className="truncate text-sm text-zinc-600 dark:text-zinc-300">{user.email}</span>
      </div>
      <button
        type="button"
        onClick={() => {
          logout();
          onAction?.();
        }}
        className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        Cerrar sesión
      </button>
    </div>
  );
}

// Desktop: a pill "Iniciar sesion" CTA (or an avatar once logged in) opens a
// small popover card instead of cramming an email input straight into the
// header row - the same login/account content also renders `inline` (no
// button/popover chrome) inside HeaderNav's mobile panel, which is already
// its own dropdown.
export function AuthMenu({ variant = "popover" }: { variant?: "popover" | "inline" }) {
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (variant !== "popover" || !open) return;

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open, variant]);

  if (loading) return <div className="h-9 w-24" />;

  const content = user ? <AccountPanel onAction={() => setOpen(false)} /> : <LoginForm />;

  if (variant === "inline") {
    return content;
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="true"
        className={
          user
            ? "flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-sm font-semibold text-white transition hover:opacity-90 dark:bg-zinc-100 dark:text-zinc-900"
            : "flex items-center gap-1.5 rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-emerald-600/30 transition hover:bg-emerald-500"
        }
      >
        {user ? (
          user.email.charAt(0).toUpperCase()
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
              <path d="M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M12 19H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Iniciar sesión
          </>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-2 w-80 rounded-xl border border-zinc-200 bg-white p-4 shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
          {content}
        </div>
      )}
    </div>
  );
}
