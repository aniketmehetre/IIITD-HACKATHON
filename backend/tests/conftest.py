"""Pytest configuration for backend test suite.

Ensures STING_ENV=test and mock keys are present so Settings validation succeeds hermetically.
"""

import os

# Configure environment before Settings instantiation
os.environ["STING_ENV"] = "test"
os.environ["TINYFISH_API_KEY"] = "test-tinyfish-api-key"
os.environ["STING_API_KEY"] = "test-sting-secret-key"
os.environ["EVIDENCE_SIGNING_KEY"] = "test-evidence-signing-key-32chars"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
