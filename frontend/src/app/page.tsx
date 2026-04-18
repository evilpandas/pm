"use client";

import { useState, type FormEvent } from "react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { KanbanBoard } from "@/components/KanbanBoard";

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authToken, setAuthToken] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error("Invalid credentials");
      }

      const data = await response.json() as { status: string; token: string };
      setAuthToken(data.token);
      setIsAuthenticated(true);
      setUsername("");
      setPassword("");
    } catch (error) {
      setError("Invalid credentials.");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="relative min-h-screen overflow-hidden">
        <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.18)_0%,_rgba(32,157,215,0.04)_55%,_transparent_70%)]" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.14)_0%,_rgba(117,57,145,0.04)_55%,_transparent_75%)]" />

        <main className="relative mx-auto flex min-h-screen max-w-[900px] items-center px-6 py-16">
          <div className="w-full rounded-[32px] border border-[var(--stroke)] bg-white/90 p-10 shadow-[var(--shadow)] backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
              Sign in
            </p>
            <h1 className="mt-4 font-display text-4xl font-semibold text-[var(--navy-dark)]">
              Welcome back to Kanban Studio
            </h1>
            <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
              Sign in to access your single-board workspace.
            </p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                  Username
                </label>
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="username"
                  className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="passphrase"
                  className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                  required
                />
              </div>
              {error ? (
                <p className="rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold text-[var(--secondary-purple)]">
                  {error}
                </p>
              ) : null}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  className="rounded-full bg-[var(--secondary-purple)] px-5 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
                >
                  Sign in
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="relative">
        <div className="absolute right-6 top-6 z-20">
          <button
            type="button"
            onClick={() => {
              setIsAuthenticated(false);
              setAuthToken("");
            }}
            className="rounded-full border border-[var(--stroke)] bg-white/90 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--navy-dark)] shadow-[var(--shadow)] transition hover:text-[var(--primary-blue)]"
          >
            Log out
          </button>
        </div>
        <KanbanBoard authToken={authToken} />
      </div>
    </ErrorBoundary>
  );
}
