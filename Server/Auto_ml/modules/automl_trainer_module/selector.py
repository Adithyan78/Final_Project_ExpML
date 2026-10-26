"""Rule-based candidate shortlisting with an explanation per model."""
from __future__ import annotations

import operator
from pathlib import Path

import yaml

from .config import TrainingConfig
from .registry import specs_for

DEFAULT_RULES_PATH = Path(__file__).with_name("rules.yaml")
_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
        "==": operator.eq, "!=": operator.ne}


def load_rules(path: str | Path | None = None) -> dict:
    rules = yaml.safe_load(Path(path or DEFAULT_RULES_PATH).read_text())
    for r in rules.get("rules", []):
        for key in ("id", "when", "points", "reason"):
            if key not in r:
                raise ValueError(f"Rule {r.get('id', '?')} is missing '{key}'.")
    return rules


def evaluate_condition(cond: dict, ctx: dict) -> bool:
    """Safe, declarative evaluator (no eval)."""
    if "all" in cond:
        return all(evaluate_condition(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(evaluate_condition(c, ctx) for c in cond["any"])
    metric, op, value = cond["metric"], cond["op"], cond["value"]
    if op not in _OPS:
        raise ValueError(f"Unsupported operator {op!r}")
    if metric not in ctx:
        raise KeyError(f"Rule references unknown context metric {metric!r}")
    actual = ctx[metric]
    return False if actual is None else bool(_OPS[op](actual, value))


def select_candidates(ctx: dict, cfg: TrainingConfig, rules: dict | None = None) -> dict:
    rules = rules or load_rules(cfg.rules_path)
    specs = specs_for(ctx["task"])
    scores = {n: {"score": 0.0, "breakdown": [], "reasons": []} for n, s in specs.items() if not s.baseline}

    for rule in rules["rules"]:
        if evaluate_condition(rule["when"], ctx):
            for name, pts in rule["points"].items():
                if name in scores:
                    scores[name]["score"] += pts
                    scores[name]["breakdown"].append({"rule_id": rule["id"], "points": pts})
                    scores[name]["reasons"].append(f"{rule['reason']} ({pts:+g})")

    excluded: dict[str, str] = {}
    for name, spec in specs.items():
        if spec.baseline:
            continue
        if name in cfg.exclude:
            excluded[name] = "Excluded by config."
        elif cfg.include_only and name not in cfg.include_only:
            excluded[name] = "Not in include_only."
        elif not spec.available:
            excluded[name] = f"Optional dependency '{spec.requires}' is not installed."
    for ex in rules.get("exclusions", []):
        if ex["model"] in scores and evaluate_condition(ex["when"], ctx):
            excluded.setdefault(ex["model"], ex["reason"])

    eligible = sorted((n for n in scores if n not in excluded), key=lambda n: scores[n]["score"], reverse=True)
    shortlist = eligible[: cfg.max_candidates]
    for n in eligible[cfg.max_candidates:]:
        excluded[n] = f"Below the top {cfg.max_candidates} by selection score."
    return {
        "context": ctx,
        "rules_version": rules.get("version"),
        "shortlist": shortlist,
        "excluded": excluded,
        "scores": {n: {"score": round(v["score"], 2), "reasons": v["reasons"], "breakdown": v["breakdown"]}
                   for n, v in scores.items()},
    }
