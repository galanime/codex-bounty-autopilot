#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    for script in scripts:
        py_compile.compile(str(script), doraise=True)
        print(f"compiled {script.relative_to(ROOT)}")

    config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    assert "wallet_id" in config, "wallet_id key is required"
    assert isinstance(config.get("active_items"), list), "active_items must be a list"
    assert config["automation"]["external_actions"] in {
        "manual_confirm",
        "auto_submit_except_wallet_withdrawal",
    }
    for asset in ("index.html", "styles.css", "app.js"):
        path = ROOT / "web" / asset
        assert path.exists(), f"missing web asset: {asset}"
        print(f"found web/{asset}")
    print("validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
