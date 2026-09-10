#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from test_helpers import SCRIPTS, run

TEMPLATES_DIR = SCRIPTS.parent / "templates"
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


class RenderBriefTests(unittest.TestCase):
    def run_render(
        self,
        template_text: str,
        context: dict[str, str],
        *extra: str,
        expected: int = 0,
    ):
        with tempfile.TemporaryDirectory() as temp:
            template_path = Path(temp) / "template.md"
            context_path = Path(temp) / "context.json"
            template_path.write_text(template_text, encoding="utf-8")
            context_path.write_text(json.dumps(context), encoding="utf-8")
            return run(
                [
                    "python3",
                    str(SCRIPTS / "render_brief.py"),
                    "--template",
                    str(template_path),
                    "--context",
                    str(context_path),
                    *extra,
                ],
                expected=expected,
            )

    def test_renders_every_template_placeholder_exactly(self) -> None:
        for template in sorted(TEMPLATES_DIR.glob("*.md")):
            with self.subTest(template=template.name):
                text = template.read_text(encoding="utf-8")
                names = sorted({match.group(1) for match in PLACEHOLDER_RE.finditer(text)})
                self.assertGreater(len(names), 0, f"{template.name} has no placeholders")
                context = {name: f"«{name}»" for name in names}
                result = self.run_render(text, context)
                expected = PLACEHOLDER_RE.sub(lambda match: f"«{match.group(1)}»", text)
                self.assertEqual(result.stdout, expected)
                self.assertNotIn("{{", result.stdout)
                for name in names:
                    self.assertIn(f"«{name}»", result.stdout)

    def test_missing_placeholder_fails_closed(self) -> None:
        result = self.run_render("hello {{name}}", {}, expected=2)
        self.assertIn("name", result.stderr)

    def test_allow_missing_substitutes_empty_with_warning(self) -> None:
        result = self.run_render("hello {{name}}", {}, "--allow-missing")
        self.assertEqual(result.stdout, "hello ")
        self.assertIn("WARNING", result.stderr)
        self.assertIn("name", result.stderr)

    def test_unused_context_key_warns_but_succeeds(self) -> None:
        result = self.run_render("hello {{name}}", {"name": "world", "extra": "unused"})
        self.assertEqual(result.stdout, "hello world")
        self.assertIn("WARNING", result.stderr)
        self.assertIn("extra", result.stderr)

    def test_output_flag_writes_file_with_parents(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            template_path = Path(temp) / "template.md"
            context_path = Path(temp) / "context.json"
            output_path = Path(temp) / "nested" / "dir" / "brief.md"
            template_path.write_text("hi {{who}}", encoding="utf-8")
            context_path.write_text(json.dumps({"who": "you"}), encoding="utf-8")
            run(
                [
                    "python3",
                    str(SCRIPTS / "render_brief.py"),
                    "--template",
                    str(template_path),
                    "--context",
                    str(context_path),
                    "--output",
                    str(output_path),
                ]
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), "hi you")


if __name__ == "__main__":
    unittest.main()
