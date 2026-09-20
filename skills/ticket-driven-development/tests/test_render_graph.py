#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_helpers import run

RENDER = ["/usr/bin/env", "python3", str(Path(__file__).resolve().parents[1] / "scripts" / "render_graph.py")]

TICKETS = {
    "tickets": [
        {
            "id": "01",
            "title": "Establish session boundary",
            "risk": "low",
            "status": "done",
            "blockers": [],
        },
        {
            "id": "02",
            "title": "Add passwordless sign-in",
            "risk": "high",
            "status": "ready-for-agent",
            "blockers": ["01"],
        },
    ],
    "ready_frontier": ["02"],
    "valid": True,
}


class RenderGraphTests(unittest.TestCase):
    def render(self, index: dict) -> str:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index_path = root / "ticket-index.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            output = root / "out" / "ticket-graph.md"
            run(RENDER + [str(index_path), "--output", str(output)])
            return output.read_text(encoding="utf-8")

    def test_renders_edges_styles_and_frontier(self) -> None:
        text = self.render(TICKETS)
        self.assertIn("graph TD", text)
        self.assertIn('01["01: Establish session boundary [low, done]"]', text)
        self.assertIn("01 --> 02", text)
        self.assertIn("style 02 fill:#f8d7da", text)
        self.assertIn("style 01 fill:#e9ecef", text)
        self.assertIn("ready frontier: 02", text)
        self.assertIn("index valid: True", text)

    def test_survives_missing_metadata(self) -> None:
        text = self.render({"tickets": [{"id": "01", "title": "", "risk": None, "status": None, "blockers": []}]})
        self.assertIn('01["01"]', text)
        self.assertIn("ready frontier: none", text)
        self.assertNotIn("style 01", text)

    def test_rejects_non_index_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            index_path = Path(temp) / "bad.json"
            index_path.write_text('{"nope": true}', encoding="utf-8")
            run(
                RENDER + [str(index_path), "--output", str(Path(temp) / "out.md")],
                expected=1,
            )

    def test_quotes_are_sanitized(self) -> None:
        text = self.render({"tickets": [{"id": "01", "title": 'Handle "quoted" input', "blockers": []}]})
        self.assertIn("01: Handle 'quoted' input", text)


if __name__ == "__main__":
    unittest.main()
