"""Write the OpenAPI document to web/openapi.json (docs/FRONTEND.md §3.1).

Usage: uv run python scripts/export_openapi.py [--check]
--check exits 1 if web/openapi.json is out of date instead of writing it.
"""

import json
import sys
from pathlib import Path

from jobsearcher.web.app import create_app

OUT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def render() -> str:
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT} er utdatert. Kjør scripts/export_openapi.py.")
            return 1
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Skrev {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
