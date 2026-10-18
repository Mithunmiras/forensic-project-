import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useSystemStatus } from "../hooks";
import { API_BASE } from "../lib/api";

const NAV = [
  { to: "/", label: "Overview", icon: "M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10" },
  { to: "/assistant", label: "AI Analytics", icon: "M8 10h8M8 14h5M21 12a9 9 0 11-4-7.5L21 3v5h-5" },
  { to: "/predict", label: "Sales Prediction", icon: "M3 17l6-6 4 4 8-8M15 7h6v6" },
  { to: "/knowledge", label: "Knowledge Assistant", icon: "M4 5a2 2 0 012-2h12v16H6a2 2 0 00-2 2V5zm14 14v2H6" },
  { to: "/status", label: "Data & Model Status", icon: "M4 6h16M4 12h16M4 18h10" },
  { to: "/about", label: "About", icon: "M12 8h.01M11 12h1v5h1M12 21a9 9 0 100-18 9 9 0 000 18z" },
];

function Icon({ d }: { d: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

function StatusPill() {
  const { data, isError, isLoading } = useSystemStatus();
  let tone = "bg-slate-500";
  let text = "Checking...";
  if (isError) [tone, text] = ["bg-rose-500", "API offline"];
  else if (data?.overall === "ready") [tone, text] = ["bg-emerald-500", "All systems ready"];
  else if (data?.overall === "degraded") [tone, text] = ["bg-amber-400", "Running (degraded)"];
  else if (data?.overall === "setup_required") [tone, text] = ["bg-amber-400", "Setup required"];
  else if (!isLoading) text = "Unknown";
  return (
    <NavLink to="/status" className="flex items-center gap-2 rounded-lg bg-navy-800 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-navy-700" aria-label={`System status: ${text}`}>
      <span className={`h-2.5 w-2.5 rounded-full ${tone}`} aria-hidden="true" />
      {text}
    </NavLink>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { isError } = useSystemStatus();

  const sidebar = (
    <nav aria-label="Main" className="flex h-full flex-col bg-navy-900 text-slate-300">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <img src="/favicon.svg" alt="" width="30" height="30" />
        <div>
          <p className="text-base font-bold leading-tight text-white">RetailIQ</p>
          <p className="text-[11px] leading-tight text-slate-400">Decision Intelligence</p>
        </div>
      </div>
      <ul className="flex-1 space-y-1 px-3 py-2">
        {NAV.map((n) => (
          <li key={n.to}>
            <NavLink
              to={n.to}
              end={n.to === "/"}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-brand-600 text-white" : "hover:bg-navy-800 hover:text-white"}`
              }
            >
              <Icon d={n.icon} />
              {n.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="space-y-2 p-3">
        <StatusPill />
        <p className="px-1 text-[11px] text-slate-500">Global Superstore · 2011-2014</p>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen lg:block">{sidebar}</aside>

      <div className="sticky top-0 z-30 flex items-center justify-between bg-navy-900 px-4 py-3 text-white lg:hidden">
        <span className="font-bold">RetailIQ</span>
        <button type="button" className="rounded-md p-2 hover:bg-navy-800" aria-expanded={open} aria-label="Toggle navigation" onClick={() => setOpen((o) => !o)}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-20 lg:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-slate-900/50" />
          <div className="absolute left-0 top-0 h-full w-64 pt-12" onClick={(e) => e.stopPropagation()}>
            {sidebar}
          </div>
        </div>
      )}

      <main id="main" className="min-w-0 px-4 py-6 sm:px-8 lg:py-8">
        {isError && (
          <div role="alert" className="mb-6 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            <p className="font-semibold">The RetailIQ API is not reachable{API_BASE ? ` at ${API_BASE}` : ""}.</p>
            <p className="mt-1">
              Start the backend in a terminal: <code className="rounded bg-white px-1.5 py-0.5">python main.py serve</code> (or <code className="rounded bg-white px-1.5 py-0.5">scripts\start_backend.ps1</code>), then reload this page.
              No figures are displayed while it is offline.
            </p>
          </div>
        )}
        <div className="mx-auto max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
