from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(*parts: str) -> Any:
    fixture_path = FIXTURES_DIR.joinpath(*parts)
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)
