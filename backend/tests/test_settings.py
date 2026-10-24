"""Unit tests for Settings validation and fail-fast behavior (Section 1)."""

from pathlib import Path

import pytest

from app.config import Settings


def test_settings_fails_fast_when_missing_required_in_non_test_mode(monkeypatch):
    """Confirm Settings raises a clear ValueError naming missing variables in non-test mode."""
    # Ensure environment variables are clear
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    monkeypatch.delenv("STING_API_KEY", raising=False)
    monkeypatch.delenv("EVIDENCE_SIGNING_KEY", raising=False)
    monkeypatch.setenv("STING_ENV", "production")

    with pytest.raises(ValueError) as exc_info:
        Settings(
            STING_ENV="production",
            TINYFISH_API_KEY=None,
            STING_API_KEY=None,
            EVIDENCE_SIGNING_KEY=None,
        )

    error_msg = str(exc_info.value)
    assert "Missing required environment variable" in error_msg
    assert "TINYFISH_API_KEY" in error_msg
    assert "STING_API_KEY" in error_msg
    assert "EVIDENCE_SIGNING_KEY" in error_msg


def test_settings_succeeds_in_test_mode_without_real_secrets(monkeypatch):
    """Confirm Settings automatically populates test defaults when STING_ENV=test."""
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    monkeypatch.delenv("STING_API_KEY", raising=False)
    monkeypatch.delenv("EVIDENCE_SIGNING_KEY", raising=False)

    settings = Settings(
        STING_ENV="test",
        TINYFISH_API_KEY=None,
        STING_API_KEY=None,
        EVIDENCE_SIGNING_KEY=None,
    )

    assert settings.STING_ENV == "test"
    assert settings.TINYFISH_API_KEY == "test-tinyfish-api-key"
    assert settings.STING_API_KEY == "test-sting-secret-key"
    assert settings.EVIDENCE_SIGNING_KEY == "test-evidence-signing-key-32chars"
    assert settings.PROXY_COUNTRY == "IN"
    assert settings.AGENT_DAILY_BUDGET == 20
    assert settings.AGENT_MAX_STEPS == 40
    assert settings.AGENT_MAX_SECONDS == 180
    assert settings.DEMO_REPLAY is False
    assert settings.SITE_REUSE_DAYS == 7
    assert settings.PIPELINE_RUNNER == "inprocess"
    assert isinstance(settings.STORAGE_DIR, Path)
