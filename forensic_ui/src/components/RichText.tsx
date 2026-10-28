import { Fragment } from "react";

interface Props {
  text: string;
  active: number | null;
  onCite: (id: number) => void;
}

/** Renders **bold** and [n] citation markers; markers are buttons that highlight the source. */
export default function RichText({ text, active, onCite }: Props) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const bold = part.match(/^\*\*(.+)\*\*$/);
        if (bold) return <strong key={i}>{bold[1]}</strong>;
        const cite = part.match(/^\[(\d+)\]$/);
        if (cite) {
          const id = Number(cite[1]);
          return (
            <button
              key={i}
              className={`cite ${active === id ? "on" : ""}`}
              onClick={() => onCite(id)}
              title="Show source"
            >
              {id}
            </button>
          );
        }
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}
