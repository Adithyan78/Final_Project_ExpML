"""Load a versioned YAML rules file (from a path or an in-memory dict/str)
into a validated RuleSet."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from .exceptions import RuleValidationError
from .rule_schema import RuleSet, validate_and_build_ruleset


def load_ruleset(
    source: Union[str, Path, Dict[str, Any]],
    known_actions: Optional[set] = None,
) -> RuleSet:
    """Load rules from a YAML file path, a raw YAML string, or an
    already-parsed dict, and validate them.

    Accepting all three forms keeps the engine convenient to use both in
    production (a versioned .yaml file on disk) and in tests (inline
    dicts/strings), without duplicating validation logic.
    """
    def _looks_like_path(value: str) -> bool:
        # A YAML *document* (what most callers pass inline, e.g. in tests)
        # contains newlines and is typically far longer than any real
        # filesystem path; checking this first avoids ever handing a
        # multi-line string to Path.exists(), which can raise on some
        # platforms for absurdly long "paths".
        return "\n" not in value and len(value) < 4096

    if isinstance(source, dict):
        raw = source
    elif isinstance(source, Path) or (isinstance(source, str) and _looks_like_path(source)):
        candidate = Path(str(source))
        if candidate.exists() and candidate.is_file():
            with open(candidate, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        elif isinstance(source, Path):
            raise RuleValidationError(f"Rules file not found: {candidate}")
        else:
            raw = yaml.safe_load(source)
    elif isinstance(source, str):
        raw = yaml.safe_load(source)
    else:
        raise RuleValidationError(f"Cannot load rules from object of type {type(source)!r}.")

    if raw is None:
        raise RuleValidationError("Rules source parsed to an empty document.")

    return validate_and_build_ruleset(raw, known_actions=known_actions)
