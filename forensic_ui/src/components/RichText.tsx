import { Fragment } from "react";
import { Citation } from "../api";

interface Props {
  text: string;
  active: number | null;
  onCite: (id: number) => void;
  citations?: Citation[];
}

/** Renders **bold** and [n] citation markers; markers are buttons that open the source. */
export default function RichText({ text, active, onCite, citations }: Props) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const bold = part.match(/^\*\*(.+)\*\*$/);
        if (bold) return <strong key={i}>{bold[1]}</strong>;
        const cite = part.match(/^\[(\d+)\]$/);
        if (cite) {
          const id = Number(cite[1]);
          const src = citations?.find((c) => c.id === id);
          return (
            <button key={i} className={`cite ${active === id ? "on" : ""}`} onClick={() => onCite(id)}
              title={src ? `${src.label}: ${src.detail}` : "Show source"}>
              {id}
            </button>
          );
        }
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}
