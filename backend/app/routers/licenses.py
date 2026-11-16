"""Licence register for music, sound effects, voices, fonts, logos and models."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db

router = APIRouter(prefix="/api/licenses", tags=["licenses"])


class LicenseIn(BaseModel):
    asset_type: Literal["music", "sfx", "voice", "font", "logo", "model", "other"]
    name: str = Field(min_length=1, max_length=200)
    license_name: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=1000)
    license_url: str | None = Field(default=None, max_length=1000)
    allows_commercial: bool = False
    attribution_required: bool = False
    attribution_text: str | None = Field(default=None, max_length=2000)
    file_path: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=5000)


def _out(row) -> dict:
    d = dict(row)
    d["allows_commercial"] = bool(d["allows_commercial"])
    d["attribution_required"] = bool(d["attribution_required"])
    return d


@router.get("")
def list_licenses():
    with db.connect() as conn:
        return [_out(r) for r in conn.execute("SELECT * FROM licenses ORDER BY asset_type, name")]


@router.post("", status_code=201)
def create_license(body: LicenseIn):
    if body.attribution_required and not (body.attribution_text or "").strip():
        raise HTTPException(status_code=400, detail="Please enter the attribution text this licence requires.")
    now = db.utcnow()
    data = body.model_dump()
    data["allows_commercial"] = int(data["allows_commercial"])
    data["attribution_required"] = int(data["attribution_required"])
    data.update(created_at=now, updated_at=now)
    cols = ", ".join(data)
    with db.connect() as conn:
        row = conn.execute(
            f"INSERT INTO licenses ({cols}) VALUES ({', '.join('?' for _ in data)}) RETURNING *",
            tuple(data.values()),
        ).fetchone()
    return _out(row)


@router.delete("/{license_id}")
def delete_license(license_id: int):
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Licence not found.")
    return {"deleted": True}
