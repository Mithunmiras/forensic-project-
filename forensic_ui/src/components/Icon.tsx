const PATHS: Record<string, string> = {
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6",
  check: "M9 12l2 2 4-4M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8h.01",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
  auto: "M4 5h16v11H4zM8 20h8M12 16v4",
  chart: "M4 19h16M7 16V10M12 16V6M17 16v-4",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5",
  list: "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
  link: "M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1",
  trace: "M5 5h4v4H5zM15 5h4v4h-4zM10 15h4v4h-4zM7 9v3h10V9M12 12v3",
  what: "M4 19h16M7 16v-5M12 16V8M17 16v-8",
  why: "M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM20 20l-5.6-5.6",
  next: "M3 17l6-6 4 4 8-8M15 7h6v6",
  todo: "M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9",
  chevron: "M6 9l6 6 6-6",
  close: "M6 6l12 12M18 6L6 18",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  filter: "M4 5h16l-6 8v6l-4-2v-4z",
};

export default function Icon({ name, size = 18 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
