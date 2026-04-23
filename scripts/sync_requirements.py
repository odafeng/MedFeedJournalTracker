#!/usr/bin/env python3
"""Regenerate requirements.txt from pyproject.toml runtime dependencies.

Run after editing [project].dependencies in pyproject.toml:

    python3 scripts/sync_requirements.py

Render's default Python buildpack uses requirements.txt, while local
dev uses `uv pip install -e .` reading pyproject.toml. Keep both in
sync by running this.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
REQUIREMENTS = ROOT / "requirements.txt"

HEADER = [
    "# Auto-generated from pyproject.toml [project].dependencies",
    "# DO NOT EDIT BY HAND — run: python3 scripts/sync_requirements.py",
    "# Render uses this file; local dev can use 'uv pip install -e .' instead.",
    "",
]


def main() -> int:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]

    lines = list(HEADER) + list(deps) + [""]
    REQUIREMENTS.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(deps)} dependencies to {REQUIREMENTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
