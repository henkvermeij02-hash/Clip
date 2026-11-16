"""Read and write user settings stored in SQLite."""

from __future__ import annotations

from typing import Any

from . import config, db


def get_all() -> dict[str, Any]:
    values = {key: spec.default for key, spec in config.DEFAULT_SETTINGS.items()}
    with db.connect() as conn:
        for row in conn.execute("SELECT key, value_json FROM settings"):
            if row["key"] in values:
                values[row["key"]] = db.loads(row["value_json"], values[row["key"]])
    return values


def get(key: str) -> Any:
    spec = config.DEFAULT_SETTINGS[key]
    with db.connect() as conn:
        row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
    return db.loads(row["value_json"], spec.default) if row else spec.default


def update(changes: dict[str, Any]) -> dict[str, Any]:
    """Validate all changes first, then save them together. Raises ValueError."""
    cleaned = {key: config.coerce_setting(key, value) for key, value in changes.items()}
    if "short_min_seconds" in cleaned or "short_max_seconds" in cleaned:
        current = get_all()
        lo = cleaned.get("short_min_seconds", current["short_min_seconds"])
        hi = cleaned.get("short_max_seconds", current["short_max_seconds"])
        if lo >= hi:
            raise ValueError("Minimum clip length must be shorter than the maximum Short length.")
    now = db.utcnow()
    with db.transaction() as conn:
        for key, value in cleaned.items():
            conn.execute(
                "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at",
                (key, db.dumps(value), now),
            )
    return get_all()


def schema() -> list[dict[str, Any]]:
    """Describe settings for the dashboard's settings form."""
    return [
        {
            "key": key,
            "default": spec.default,
            "type": spec.type.__name__,
            "group": spec.group,
            "label": spec.label,
            "help": spec.help,
            "phase": spec.phase,
            "choices": list(spec.choices) if spec.choices else None,
            "minimum": spec.minimum,
            "maximum": spec.maximum,
        }
        for key, spec in config.DEFAULT_SETTINGS.items()
    ]
