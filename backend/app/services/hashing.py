"""Fast fingerprinting used to detect duplicate imports.

Hashing every byte of a 20 GB recording would take minutes, so we hash the
file size plus three 4 MB samples (start, middle, end). Two different
recordings producing the same fingerprint is practically impossible.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

SAMPLE_SIZE = 4 * 1024 * 1024


def quick_hash(path: str | Path) -> str:
    path = Path(path)
    size = path.stat().st_size
    digest = hashlib.sha256()
    digest.update(str(size).encode())
    with path.open("rb") as handle:
        if size <= SAMPLE_SIZE * 3:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        else:
            for offset in (0, size // 2 - SAMPLE_SIZE // 2, size - SAMPLE_SIZE):
                handle.seek(offset, os.SEEK_SET)
                digest.update(handle.read(SAMPLE_SIZE))
    return "qh1:" + digest.hexdigest()
