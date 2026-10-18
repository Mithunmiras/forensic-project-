from pathlib import Path

from src.rag.documents import (
    Document,
    chunk_document,
    clean_text,
    discover_documents,
    is_indexable,
    load_documents,
    redact_secrets,
)


def make_tree(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n\nHello world, this is the guide document for tests.\n")
    (root / "docs" / "notes.txt").write_text("Plain text notes about the retail dataset and its columns.")
    (root / "README.md").write_text("# Readme\n\nProject readme with enough content to index properly.")
    (root / ".env").write_text("DATABASE_URL=postgresql://u:supersecret@h/db\n")
    (root / ".env.local").write_text("TOKEN=abc")
    (root / "key.pem").write_text("-----BEGIN PRIVATE KEY-----")
    for d in (".git", ".venv", "node_modules", "models", "vectorstore", "__pycache__", "data"):
        (root / d).mkdir()
        (root / d / "leak.md").write_text("# Should never be indexed\n\nsecret content here that is long enough")
    (root / "models" / "m.joblib").write_bytes(b"\x00\x01")
    (root / "docs" / "image.png").write_bytes(b"\x89PNG")


def test_discovery_excludes_secrets_binaries_and_tooling(tmp_path):
    make_tree(tmp_path)
    found = {p.relative_to(tmp_path).as_posix() for p in discover_documents(
        ["README.md", "docs/**/*.md", "docs/**/*.txt", "**/*.md", ".env", "*.pem", "../*"], tmp_path)}
    assert found == {"README.md", "docs/guide.md", "docs/notes.txt"}


def test_is_indexable_rules(tmp_path):
    make_tree(tmp_path)
    assert is_indexable(tmp_path / "README.md", tmp_path)
    assert not is_indexable(tmp_path / ".env", tmp_path)
    assert not is_indexable(tmp_path / "key.pem", tmp_path)
    assert not is_indexable(tmp_path / "models" / "leak.md", tmp_path)
    assert not is_indexable(Path(__file__), tmp_path)  # outside the root


def test_absolute_and_parent_patterns_are_ignored(tmp_path):
    make_tree(tmp_path)
    assert discover_documents(["/etc/passwd", "../x", "..\\x"], tmp_path) == []


def test_secrets_are_redacted():
    text = "url postgresql://user:hunter2@host/db and password = Sup3rSecret! and api_key: sk-abcdefghijklmnopqrstuv"
    out = redact_secrets(text)
    assert "hunter2" not in out and "Sup3rSecret" not in out and "abcdefghijklmnop" not in out
    assert "user" in out and "host/db" in out


def test_clean_text_normalises():
    assert clean_text("a\r\n\r\n\r\n\r\nb \t\n") == "a\n\nb"


def test_load_documents_hashes_and_relative_paths(tmp_path):
    make_tree(tmp_path)
    docs = load_documents(discover_documents(["docs/*.md"], tmp_path), tmp_path)
    assert docs[0].source == "docs/guide.md" and len(docs[0].sha256) == 64


def test_chunking_respects_headings_size_and_overlap():
    body = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(12))
    doc = Document("docs/x.md", f"# Title\n\nIntro text that is long enough to keep.\n\n## Section A\n\n{body}\n\n## Section B\n\nShort but valid section body text.", "h")
    chunks = chunk_document(doc, max_chars=500, overlap=80)
    assert len(chunks) > 3
    assert all(len(c.text) <= 500 + 80 + 10 for c in chunks)
    assert {c.heading for c in chunks} >= {"Title", "Title > Section A", "Title > Section B"}
    assert len({c.id for c in chunks}) == len(chunks)
    a = [c for c in chunks if c.heading.endswith("Section A")]
    assert any(a[i].text[:30].split()[0] in a[i - 1].text for i in range(1, len(a)))  # overlap carried over


def test_bullet_lists_are_split_per_item():
    items = "\n".join(f"- **Metric {i}** - definition number {i} " + "text " * 20 for i in range(10))
    chunks = chunk_document(Document("docs/d.md", f"# Defs\n\n{items}", "h"), max_chars=300, overlap=0)
    assert len(chunks) >= 5
    assert all(c.text.count("**Metric") <= 3 for c in chunks)


def test_code_fences_do_not_create_headings():
    doc = Document("docs/c.md", "# Real\n\nSome intro paragraph with sufficient length.\n\n```\n# not a heading\nprint(1)\n```\n", "h")
    assert {c.heading for c in chunk_document(doc)} == {"Real"}


def test_tiny_fragments_are_dropped():
    assert chunk_document(Document("docs/t.md", "# T\n\nhi", "h")) == []
