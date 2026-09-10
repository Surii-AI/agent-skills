#!/usr/bin/env python3
"""Render a worker brief template from a flat JSON placeholder context.

Every ``{{ name }}`` occurrence in the template is replaced by the context
value of the same name. A placeholder missing from the context is an input
error (exit 2) unless ``--allow-missing`` substitutes the empty string; a
context key the template never uses is a warning, because it usually means
the template and the controller's context builder have drifted apart.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path, help="brief template path")
    parser.add_argument("--context", required=True, type=Path, help="flat JSON object: placeholder name to value")
    parser.add_argument("--output", type=Path, help="write the rendered brief here instead of stdout")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="substitute an empty string for missing placeholders instead of failing",
    )
    args = parser.parse_args()

    try:
        template = args.template.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: cannot read template: {error}", file=sys.stderr)
        return 2
    try:
        raw_context = json.loads(args.context.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"error: cannot read context: {error}", file=sys.stderr)
        return 2
    if not isinstance(raw_context, dict):
        print("error: context must be a flat JSON object", file=sys.stderr)
        return 2
    context: dict[str, str] = {}
    for key, value in raw_context.items():
        if isinstance(value, (dict, list)):
            print(f"error: context value for '{key}' must be a scalar", file=sys.stderr)
            return 2
        context[key] = value if isinstance(value, str) else json.dumps(value)

    used = {match.group(1) for match in PLACEHOLDER_RE.finditer(template)}
    missing = sorted(used - context.keys())
    if missing and not args.allow_missing:
        print("error: missing context values for placeholders: " + ", ".join(missing), file=sys.stderr)
        return 2
    for name in missing:
        print(f"WARNING: placeholder '{name}' missing from context; substituted empty string", file=sys.stderr)
        context[name] = ""
    for key in sorted(context.keys() - used):
        print(f"WARNING: context key '{key}' is not used by the template", file=sys.stderr)

    rendered = PLACEHOLDER_RE.sub(lambda match: context[match.group(1)], template)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
