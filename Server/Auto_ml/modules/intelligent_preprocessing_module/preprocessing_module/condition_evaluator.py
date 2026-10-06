"""Safe evaluator for rule `condition` strings, e.g.:

    "column.missing_pct > 60"
    "column.type == 'numeric' and 5 < column.missing_pct <= 60"
    "column.type == 'categorical' and column.cardinality > 20"
    "'high_missing' in column.flags"

Conditions come from a YAML file that is (in principle) editable outside of
code review, so we do NOT use Python's `eval` on arbitrary input. Instead we
parse the expression into an AST and walk it against a strict whitelist of
node types before ever evaluating it. Only attribute access on the single
name `column` is permitted; no function calls, no comprehensions, no
subscription of arbitrary objects, no imports, nothing that could execute
side-effecting code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict

from .exceptions import ConditionEvaluationError

# AST node types that are allowed to appear anywhere in a condition.
_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Compare,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
    ast.Attribute,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
)

_ALLOWED_ROOT_NAME = "column"


class ColumnContext:
    """A read-only, attribute-accessible view over a single column's
    profile facts, as exposed to rule conditions under the name `column`.

    Unknown attributes resolve to `None` rather than raising, so that a
    condition referencing an attribute that happens to be absent for a
    given column (e.g. `column.skew` on a categorical column) evaluates
    to a well-defined falsy-ish value instead of blowing up the whole
    rule pass. Comparisons against `None` are still valid comparisons
    below (e.g. `None > 60` raises a normal TypeError) but that is
    surfaced clearly during fit(), not swallowed.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Dict[str, Any]):
        object.__setattr__(self, "_data", dict(data))

    def __getattr__(self, item: str) -> Any:
        # __getattr__ is only invoked when normal attribute lookup fails,
        # so this covers every field pulled from the analyzer profile.
        return self._data.get(item, None)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"ColumnContext({self._data!r})"


def _validate_ast(node: ast.AST, raw_condition: str) -> None:
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_NODES):
            raise ConditionEvaluationError(
                f"Disallowed expression element {type(child).__name__!r} "
                f"in condition: {raw_condition!r}"
            )
        if isinstance(child, ast.Name) and child.id != _ALLOWED_ROOT_NAME:
            raise ConditionEvaluationError(
                f"Condition may only reference the name "
                f"{_ALLOWED_ROOT_NAME!r}, found {child.id!r} in: "
                f"{raw_condition!r}"
            )
        if isinstance(child, ast.Attribute):
            # Only simple `column.attr` chains are allowed (no
            # `column.attr.attr2`, no attribute access on anything but
            # the `column` name itself, and no dunder/private attributes
            # that could be used to reach back into Python internals).
            if not isinstance(child.value, ast.Name) or child.value.id != _ALLOWED_ROOT_NAME:
                raise ConditionEvaluationError(
                    f"Only direct attribute access on 'column' is allowed "
                    f"in: {raw_condition!r}"
                )
            if child.attr.startswith("_"):
                raise ConditionEvaluationError(
                    f"Access to private/dunder attribute {child.attr!r} is not "
                    f"allowed in: {raw_condition!r}"
                )


def compile_condition(raw_condition: str) -> ast.Expression:
    """Parse + validate a condition string, returning a compiled-safe AST.

    Raises ConditionEvaluationError on any syntax error or disallowed
    construct. Call this once per rule at load time so problems surface
    at validation time rather than deep inside a fit() call.
    """
    try:
        tree = ast.parse(raw_condition, mode="eval")
    except SyntaxError as exc:
        raise ConditionEvaluationError(
            f"Could not parse condition {raw_condition!r}: {exc}"
        ) from exc
    _validate_ast(tree, raw_condition)
    return tree


@dataclass
class CompiledCondition:
    raw: str
    _code: Any  # compiled code object

    @classmethod
    def build(cls, raw_condition: str) -> "CompiledCondition":
        tree = compile_condition(raw_condition)
        code = compile(tree, filename="<rule-condition>", mode="eval")
        return cls(raw=raw_condition, _code=code)

    def evaluate(self, column_facts: Dict[str, Any]) -> bool:
        context = ColumnContext(column_facts)
        try:
            result = eval(  # noqa: S307 - restricted by AST whitelist above
                self._code, {"__builtins__": {}}, {"column": context}
            )
        except ConditionEvaluationError:
            raise
        except Exception as exc:
            raise ConditionEvaluationError(
                f"Error evaluating condition {self.raw!r} for column "
                f"facts {column_facts!r}: {exc}"
            ) from exc
        return bool(result)
