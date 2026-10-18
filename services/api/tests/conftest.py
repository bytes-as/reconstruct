"""Test defaults so importing the app does not depend on a developer shell."""

import os

os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("PUBLISHER_SALT", "test-publisher-salt")
os.environ.setdefault("FALKORDB_HOST", os.environ.get("FALKORDB_HOST", "falkordb"))
os.environ.setdefault("FALKORDB_PORT", os.environ.get("FALKORDB_PORT", "6379"))
