"""Softly Knowledge build pipeline.

Validates the Markdown atoms against the schema + editorial invariants and
compiles the published subset into an offline, read-only SQLite store with FTS5.

Run with:  python3 -m pipeline.build
"""

__version__ = "1"
