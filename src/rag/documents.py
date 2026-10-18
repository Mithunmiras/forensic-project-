"""Document discovery, text extraction, cleaning and chunking for the knowledge base."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import ROOT

SUPPORTED_SUFFIXES = {".md", ".txt", ".rst", ".sql"}
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__", "models", "vectorstore", ".pgdata",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache", "chroma", "data", "reports",
}
EXCLUDED_NAME_PREFIXES = (".env",)
EXCLUDED_SUFFIXES = {".pkl", ".joblib", ".pem", ".key", ".crt", ".p12", ".sqlite", ".db", ".pyc", ".log"}
MAX_FILE_BYTES = 1_000_000

_SECRET_PATTERNS = [
    (re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)([^@\s]+)(@)"), r"\1***\3"),
    (re.compile(r"(?i)\b(password|passwd|pwd|api[_-]?key|secret|token)\b(\s*[=:]\s*)(?!\*\*\*)([^\s,;'\"`]{4,})"), r"\1\2***"),
    (re.compile(r"\b(sk|pk|ghp|xox[abp])-[A-Za-z0-9_-]{16,}\b"), "***"),
]


class ExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Document:
    source: str        # path relative to the project root, forward slashes
    text: str
    sha256: str


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    heading: str
    index: int
    text: str


def redact_secrets(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return redact_secrets(text).strip()


def is_indexable(path: Path, root: Path = ROOT) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False  # never index files outside the project
    if any(part in EXCLUDED_DIRS for part in rel.parts[:-1]):
        # allow docs/generated etc. but never excluded dirs; "data"/"reports" are excluded above
        return False
    name = path.name
    if name.startswith(EXCLUDED_NAME_PREFIXES) or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return path.suffix.lower() in SUPPORTED_SUFFIXES and path.is_file()


def discover_documents(sources: list[str], root: Path = ROOT) -> list[Path]:
    """Expand glob patterns (relative to the project root) into indexable files."""
    found: dict[str, Path] = {}
    for pattern in sources:
        pattern = pattern.strip()
        if not pattern or pattern.startswith(("/", "\\")) or ".." in Path(pattern).parts:
            continue
        for path in root.glob(pattern):
            if is_indexable(path, root) and path.stat().st_size <= MAX_FILE_BYTES:
                found[str(path.resolve())] = path
    return sorted(found.values(), key=lambda p: str(p).lower())


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractionError(f"Unsupported file type: {suffix}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def load_documents(paths: list[Path], root: Path = ROOT) -> list[Document]:
    docs: list[Document] = []
    for path in paths:
        text = clean_text(extract_text(path))
        if not text:
            continue
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        docs.append(Document(source=rel, text=text, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()))
    return docs


# ----------------------------------------------------------------------------- chunking
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _split_sections(text: str, default_heading: str) -> list[tuple[str, str]]:
    """Split markdown into (heading path, body) sections. Non-markdown text is one section."""
    sections: list[tuple[str, list[str]]] = []
    stack: list[tuple[int, str]] = []
    current: list[str] = []
    heading = default_heading
    in_fence = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            if current and "".join(current).strip():
                sections.append((heading, current))
            level, title = len(m.group(1)), m.group(2)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            heading = " > ".join(t for _, t in stack)
            current = []
        else:
            current.append(line)
    if current and "".join(current).strip():
        sections.append((heading, current))
    return [(h, "\n".join(body).strip()) for h, body in sections if "\n".join(body).strip()]


def _pack(paragraphs: list[str], max_chars: int, overlap: int) -> list[str]:
    """Greedily pack paragraphs into <= max_chars windows with word-aligned overlap."""
    pieces: list[str] = []
    for p in paragraphs:
        while len(p) > max_chars:  # hard-split oversized paragraphs at sentence/space boundaries
            cut = max(p.rfind(". ", 0, max_chars), p.rfind("\n", 0, max_chars), p.rfind(" ", 0, max_chars))
            cut = cut + 1 if cut > max_chars // 3 else max_chars
            pieces.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            pieces.append(p)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chars:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            if tail:
                tail = tail[tail.find(" ") + 1:] if " " in tail else tail  # start on a word boundary
            current = (tail + "\n\n" + piece).strip() if tail else piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def chunk_document(doc: Document, max_chars: int = 900, overlap: int = 150) -> list[Chunk]:
    default_heading = Path(doc.source).name
    chunks: list[Chunk] = []
    for heading, body in _split_sections(doc.text, default_heading):
        paragraphs: list[str] = []
        for block in (b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()):
            # A bullet/numbered list is split item by item so one chunk does not mix many topics.
            if re.match(r"([-*+]\s|\d+\.\s)", block) and "```" not in block:
                paragraphs += [i.strip() for i in re.split(r"\n(?=(?:[-*+]|\d+\.)\s)", block) if i.strip()]
            else:
                paragraphs.append(block)
        for text in _pack(paragraphs, max_chars, overlap):
            if len(text) < 30:
                continue
            idx = len(chunks)
            digest = hashlib.sha1(f"{doc.source}|{idx}|{text}".encode("utf-8")).hexdigest()[:16]
            chunks.append(Chunk(id=digest, source=doc.source, heading=heading, index=idx, text=text))
    return chunks
