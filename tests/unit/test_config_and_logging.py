from src.config import Settings, normalize_db_url, redact_url
from src.logging_setup import redact


def test_normalize_db_url_uses_psycopg3():
    assert normalize_db_url("postgresql://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert normalize_db_url("postgres://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert normalize_db_url("postgresql+psycopg://u@h/d") == "postgresql+psycopg://u@h/d"


def test_redact_url_hides_password():
    assert redact_url("postgresql://bob:s3cret@localhost:5432/db") == "postgresql://bob:***@localhost:5432/db"
    assert redact_url("postgresql://bob@localhost/db") == "postgresql://bob@localhost/db"
    assert redact_url(None) is None


def test_redact_free_text():
    text = "connect postgresql://u:hunter2@h/db password=abc123 token: xyz789"
    out = redact(text)
    assert "hunter2" not in out and "abc123" not in out and "xyz789" not in out


def test_settings_defaults_and_legacy_db_vars():
    s = Settings(_env_file=None)
    assert s.effective_database_url is None and s.effective_readonly_url is None
    legacy = Settings(db_user="postgres", db_password="p@ss word", db_name="x", _env_file=None)
    assert legacy.effective_database_url == "postgresql+psycopg://postgres:p%40ss+word@localhost:5432/x"


def test_database_url_wins_over_legacy_vars():
    s = Settings(database_url="postgresql://a@h/d", db_user="other", _env_file=None)
    assert s.effective_database_url == "postgresql+psycopg://a@h/d"


def test_cors_origins_parsing():
    s = Settings(frontend_origin="http://a.com/, http://b.com ,", _env_file=None)
    assert s.cors_origins == ["http://a.com", "http://b.com"]


def test_relative_paths_become_absolute():
    s = Settings(model_path="models/x.joblib", _env_file=None)
    assert s.model_path.is_absolute()
