"""Pure, bounded CSV queries over a previously authorized byte snapshot.

The model proposes a finite query. This module validates that proposal and
performs arithmetic itself. It has no filesystem, network, permission, formula
evaluation, Python execution, or spreadsheet-engine capability.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from decimal import (Context, Decimal, DecimalException, DivisionByZero, Inexact,
                     InvalidOperation, Overflow, Rounded, ROUND_HALF_EVEN,
                     Underflow, localcontext)
import hashlib
import json
import re


class CsvQueryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


_NAME = {"type": "string", "minLength": 1, "maxLength": 256}
_EXPRESSION = {
    "description": "One exact column, a dot-decimal constant, or binary add/sub/mul/div. Never code or spreadsheet formulas.",
    "oneOf": [
        {"type": "object", "required": ["column"], "properties": {"column": _NAME}, "additionalProperties": False},
        {"type": "object", "required": ["number"], "properties": {"number": {"type": "string", "maxLength": 64}}, "additionalProperties": False},
        {"type": "object", "required": ["op", "args"], "properties": {
            "op": {"enum": ["add", "sub", "mul", "div"]},
            "args": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/expression"}},
        }, "additionalProperties": False},
    ],
}

CSV_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_csv",
        "description": (
            "Propose a bounded query over the supplied CSV table only. Use exact column names. "
            "The host computes all numbers with Decimal; never supply an answer or invented data. "
            "derive expressions use binary add/sub/mul/div, columns or dot-decimal constants. "
            "eq/ne filters compare literal text; other filters compare strict numeric values using "
            "the user's decimal separator. No grouping separators or formula cells are interpreted. "
            "With group_by, grand_totals covers all FILTERED rows. select can retain individual rows "
            "alongside aggregates. If the request is ambiguous or cannot be represented, do not call."
        ),
        "parameters": {
            "type": "object", "additionalProperties": False,
            "$defs": {"expression": _EXPRESSION},
            "properties": {
                "select": {"type": "array", "maxItems": 128, "items": _NAME, "uniqueItems": True},
                "derive": {"type": "array", "maxItems": 8, "items": {
                    "type": "object", "required": ["name", "expression"], "additionalProperties": False,
                    "properties": {"name": _NAME, "expression": {"$ref": "#/$defs/expression"}},
                }},
                "filters": {"type": "array", "maxItems": 16, "items": {
                    "type": "object", "required": ["column", "op", "value"], "additionalProperties": False,
                    "properties": {"column": _NAME, "op": {"enum": ["eq", "ne", "gt", "gte", "lt", "lte"]},
                                   "value": {"type": "string", "maxLength": 1024}},
                }},
                "group_by": {"type": "array", "maxItems": 4, "items": _NAME, "uniqueItems": True},
                "aggregates": {"type": "array", "maxItems": 8, "items": {
                    "type": "object", "required": ["op", "as"], "additionalProperties": False,
                    "properties": {"op": {"enum": ["count", "sum", "min", "max", "mean"]},
                                   "column": _NAME, "as": _NAME},
                }},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "anyOf": [{"required": ["select"], "properties": {"select": {"minItems": 1}}},
                      {"required": ["aggregates"], "properties": {"aggregates": {"minItems": 1}}}],
        },
    },
}

MAX_PLAN_BYTES = 16384
MAX_OUTPUT_BYTES = 512 * 1024
MAX_EXPRESSION_DEPTH = 8
MAX_EXPRESSION_NODES = 128
PRECISION = 38


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fingerprint(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bounded_result_bytes(value):
    # Stop during serialization, before allocating an oversized complete JSON
    # string. Input cells are already byte-bounded and Decimal values below are
    # representation-bounded, including zero.
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    parts, size = [], 0
    for chunk in encoder.iterencode(value):
        encoded = chunk.encode("utf-8")
        size += len(encoded)
        if size > MAX_OUTPUT_BYTES:
            raise CsvQueryError("CSV_OUTPUT_LIMIT")
        parts.append(encoded)
    return b"".join(parts)


def _number(value, separator):
    if isinstance(value, Decimal):
        return value
    if not isinstance(value, str) or not value or len(value) > 64:
        raise CsvQueryError("CSV_NUMERIC_FORMAT")
    # No implicit stripping, thousands separator, exponent, currency, percent,
    # booleans, blanks, NaN, infinity, or spreadsheet formulas.
    pattern = r"[+-]?[0-9]+(?:" + re.escape(separator) + r"[0-9]+)?"
    if re.fullmatch(pattern, value) is None:
        raise CsvQueryError("CSV_NUMERIC_FORMAT")
    if sum(char.isdigit() for char in value) > 24:
        raise CsvQueryError("CSV_NUMERIC_LIMIT")
    number = Decimal(value.replace(separator, "."))
    if not number.is_finite() or abs(number.adjusted()) > 30 and number:
        raise CsvQueryError("CSV_NUMERIC_LIMIT")
    return number


def _numeric_result(value):
    # Decimal zero can retain an exponentially large negative exponent under
    # repeated multiplication. Canonicalize it before any fixed-point format.
    if value.is_zero():
        return Decimal(0)
    if not value.is_finite() or value and abs(value.adjusted()) > 30:
        raise CsvQueryError("CSV_NUMERIC_LIMIT")
    return value


def _display(value):
    if isinstance(value, Decimal):
        # Preserve meaningful fractional trailing zeros from the arithmetic;
        # avoid exponent notation and normalize negative zero.
        if value.is_zero():
            return "0"
        return format(value, "f")
    return value


def _name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise CsvQueryError("CSV_QUERY_INVALID")
    return value


def _list(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        raise CsvQueryError("CSV_QUERY_LIMIT")
    return value


def _columns(values, available, maximum):
    result = _list(values, maximum)
    for value in result:
        if _name(value) not in available:
            raise CsvQueryError("CSV_UNKNOWN_COLUMN")
    if len(set(result)) != len(result):
        raise CsvQueryError("CSV_QUERY_INVALID")
    return result


def _check_expression(expression, available, depth, budget, referenced):
    budget[0] += 1
    if depth > MAX_EXPRESSION_DEPTH or budget[0] > MAX_EXPRESSION_NODES:
        raise CsvQueryError("CSV_QUERY_LIMIT")
    if not isinstance(expression, dict):
        raise CsvQueryError("CSV_EXPRESSION_INVALID")
    if set(expression) == {"column"}:
        name = _name(expression["column"])
        if name not in available:
            raise CsvQueryError("CSV_UNKNOWN_COLUMN")
        referenced.add(name)
        return
    if set(expression) == {"number"}:
        _number(expression["number"], ".")
        return
    if set(expression) != {"op", "args"} or expression["op"] not in ("add", "sub", "mul", "div"):
        raise CsvQueryError("CSV_EXPRESSION_INVALID")
    arguments = expression["args"]
    if not isinstance(arguments, list) or len(arguments) != 2:
        raise CsvQueryError("CSV_EXPRESSION_INVALID")
    for argument in arguments:
        _check_expression(argument, available, depth + 1, budget, referenced)


def _expression_text(expression):
    if "column" in expression:
        return json.dumps(expression["column"], ensure_ascii=False)
    if "number" in expression:
        return expression["number"]
    operators = {"add": "+", "sub": "−", "mul": "×", "div": "÷"}
    left, right = expression["args"]
    return f"({_expression_text(left)} {operators[expression['op']]} {_expression_text(right)})"


def _evaluate(expression, values, separator):
    if "column" in expression:
        return _number(values[expression["column"]], separator)
    if "number" in expression:
        return _number(expression["number"], ".")
    left, right = (_evaluate(argument, values, separator) for argument in expression["args"])
    operation = expression["op"]
    if operation == "div" and right.is_zero():
        raise CsvQueryError("CSV_DIVISION_BY_ZERO")
    value = left + right if operation == "add" else left - right if operation == "sub" else left * right if operation == "mul" else left / right
    return _numeric_result(value)


def _validate_table(table):
    if not isinstance(table, dict):
        raise CsvQueryError("CSV_TABLE_INVALID")
    columns, rows = table.get("columns"), table.get("rows")
    if not isinstance(columns, list) or not 1 <= len(columns) <= 128 or not isinstance(rows, list) or len(rows) > 249:
        raise CsvQueryError("CSV_TABLE_INVALID")
    if any(not isinstance(name, str) or not name.strip() for name in columns) or len(set(columns)) != len(columns):
        raise CsvQueryError("CSV_TABLE_INVALID")
    last = 1
    for index, row in enumerate(rows, 2):
        if not isinstance(row, dict) or set(row) != {"row", "start_line", "end_line", "cells"}:
            raise CsvQueryError("CSV_TABLE_INVALID")
        if type(row["row"]) is not int or row["row"] != index:
            raise CsvQueryError("CSV_TABLE_INVALID")
        if (type(row["start_line"]) is not int or type(row["end_line"]) is not int
                or not last < row["start_line"] <= row["end_line"] <= 250):
            raise CsvQueryError("CSV_TABLE_INVALID")
        last = row["end_line"]
        if not isinstance(row["cells"], list) or len(row["cells"]) != len(columns) or any(not isinstance(cell, str) for cell in row["cells"]):
            raise CsvQueryError("CSV_TABLE_INVALID")
    return columns, rows


def _validate_plan(plan, source_columns, separator):
    try:
        encoded = _canonical(plan)
    except (ValueError, TypeError, RecursionError):
        raise CsvQueryError("CSV_QUERY_INVALID") from None
    if len(encoded) > MAX_PLAN_BYTES:
        raise CsvQueryError("CSV_QUERY_LIMIT")
    if not isinstance(plan, dict) or set(plan) - {"select", "derive", "filters", "group_by", "aggregates", "limit"}:
        raise CsvQueryError("CSV_QUERY_INVALID")
    plan = deepcopy(plan)
    for field in ("select", "derive", "filters", "group_by", "aggregates"):
        plan.setdefault(field, [])
    plan.setdefault("limit", 100)
    if type(plan["limit"]) is not int or not 1 <= plan["limit"] <= 100:
        raise CsvQueryError("CSV_QUERY_LIMIT")
    available, referenced, budget = list(source_columns), set(), [0]
    for derived in _list(plan["derive"], 8):
        if not isinstance(derived, dict) or set(derived) != {"name", "expression"}:
            raise CsvQueryError("CSV_QUERY_INVALID")
        name = _name(derived["name"])
        if name.strip().casefold() in {existing.strip().casefold() for existing in available}:
            raise CsvQueryError("CSV_COLUMN_COLLISION")
        _check_expression(derived["expression"], available, 0, budget, referenced)
        available.append(name)
    _columns(plan["select"], available, 128)
    _columns(plan["group_by"], available, 4)
    referenced.update(plan["select"] + plan["group_by"])
    for condition in _list(plan["filters"], 16):
        if not isinstance(condition, dict) or set(condition) != {"column", "op", "value"}:
            raise CsvQueryError("CSV_QUERY_INVALID")
        _columns([condition["column"]], available, 1)
        referenced.add(condition["column"])
        if condition["op"] not in ("eq", "ne", "gt", "gte", "lt", "lte"):
            raise CsvQueryError("CSV_FILTER_INVALID")
        if not isinstance(condition["value"], str) or len(condition["value"]) > 1024:
            raise CsvQueryError("CSV_FILTER_INVALID")
        if condition["op"] not in ("eq", "ne"):
            _number(condition["value"], separator)
    names = list(plan["group_by"])
    for aggregate in _list(plan["aggregates"], 8):
        if not isinstance(aggregate, dict) or set(aggregate) - {"op", "column", "as"} or not {"op", "as"} <= set(aggregate):
            raise CsvQueryError("CSV_QUERY_INVALID")
        if aggregate["op"] not in ("count", "sum", "min", "max", "mean"):
            raise CsvQueryError("CSV_AGGREGATE_INVALID")
        alias = _name(aggregate["as"])
        if alias.strip().casefold() in {name.strip().casefold() for name in names}:
            raise CsvQueryError("CSV_COLUMN_COLLISION")
        names.append(alias)
        if aggregate["op"] == "count":
            if "column" in aggregate:
                raise CsvQueryError("CSV_AGGREGATE_INVALID")
        elif "column" not in aggregate:
            raise CsvQueryError("CSV_AGGREGATE_INVALID")
        else:
            _columns([aggregate["column"]], available, 1)
            referenced.add(aggregate["column"])
    if not plan["select"] and not plan["aggregates"]:
        raise CsvQueryError("CSV_QUERY_EMPTY")
    if plan["group_by"] and not plan["aggregates"]:
        raise CsvQueryError("CSV_AGGREGATE_REQUIRED")
    return plan, referenced


def _location(row):
    return {field: row[field] for field in ("row", "start_line", "end_line")}


def _matches(values, condition, separator):
    left, right = values[condition["column"]], condition["value"]
    operation = condition["op"]
    if operation in ("eq", "ne"):
        # Derived decimals use their literal returned representation; filters
        # never silently coerce source strings for equality.
        equal = _display(left) == right
        return equal if operation == "eq" else not equal
    left, right = _number(left, separator), _number(right, separator)
    return left > right if operation == "gt" else left >= right if operation == "gte" else left < right if operation == "lt" else left <= right


def _aggregate(rows, specification, separator):
    operation = specification["op"]
    if operation == "count":
        return str(len(rows))
    values = [_number(row["values"][specification["column"]], separator) for row in rows]
    if not values:
        return "0" if operation == "sum" else None
    if operation == "min":
        value = min(values)
    elif operation == "max":
        value = max(values)
    else:
        value = sum(values, Decimal(0))
        if operation == "mean":
            value /= Decimal(len(values))
    return _display(_numeric_result(value))


def _aggregate_row(rows, aggregates, separator, values=None):
    result = dict(values or {})
    result.update({item["as"]: _aggregate(rows, item, separator) for item in aggregates})
    return {"values": result, "source_rows": [row["source"]["row"] for row in rows],
            "source_locations": [_location(row["source"]) for row in rows]}


def execute_csv_query(table, plan, *, decimal_separator="."):
    """Execute only a validated pure query against the entire bounded table.

    Calculations cover all matched rows; limit affects presentation only.
    A group total and grand total explicitly refer to the same filtered scope.
    Numeric blanks, malformed numerics and calculation failures reject the whole
    query rather than silently omitting a record or returning a partial sum.
    """
    if decimal_separator not in (".", ","):
        raise CsvQueryError("CSV_DECIMAL_SEPARATOR_INVALID")
    source_columns, source_rows = _validate_table(table)
    plan, referenced = _validate_plan(plan, source_columns, decimal_separator)
    try:
        # Do not inherit flags, traps or exponent limits from the caller. The
        # same authorized data/plan/options must always yield the same result.
        arithmetic_context = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN,
                                     Emin=-999999, Emax=999999, capitals=1, clamp=0,
                                     flags=[], traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])
        with localcontext(arithmetic_context) as context:
            matched = []
            for source in source_rows:
                values = dict(zip(source_columns, source["cells"], strict=True))
                for derived in plan["derive"]:
                    values[derived["name"]] = _evaluate(derived["expression"], values, decimal_separator)
                if all(_matches(values, condition, decimal_separator) for condition in plan["filters"]):
                    matched.append({"values": values, "source": source})
            limit = plan["limit"]
            selected = [{"values": {column: _display(row["values"][column]) for column in plan["select"]},
                         "source_rows": [row["source"]["row"]], "source_locations": [_location(row["source"])]}
                        for row in matched[:limit]] if plan["select"] else []
            grand_totals = None
            if plan["aggregates"]:
                groups = OrderedDict()
                if plan["group_by"]:
                    for row in matched:
                        key = tuple(_display(row["values"][column]) for column in plan["group_by"])
                        groups.setdefault(key, []).append(row)
                else:
                    groups[()] = matched
                results = [_aggregate_row(rows, plan["aggregates"], decimal_separator,
                                          dict(zip(plan["group_by"], key, strict=True)))
                           for key, rows in groups.items()]
                columns = plan["group_by"] + [item["as"] for item in plan["aggregates"]]
                if plan["group_by"]:
                    grand_totals = _aggregate_row(matched, plan["aggregates"], decimal_separator)
                    grand_totals["scope"] = "all_matched_rows_after_filters"
            else:
                results, columns = selected, plan["select"]
            total_result_rows = len(results) if plan["aggregates"] else len(matched)
            rounded = bool(context.flags[Inexact] or context.flags[Rounded])
    except DecimalException:
        raise CsvQueryError("CSV_NUMERIC_LIMIT") from None
    result = {
        "schema": "csv-query.result.v1", "plan": plan,
        "interpretation": {
            "derived": [{**item, "text": _expression_text(item["expression"])} for item in plan["derive"]],
            "filters": plan["filters"], "filter_combination": "all",
            "group_by": plan["group_by"], "aggregates": plan["aggregates"],
            "decimal_separator": decimal_separator,
            "constant_decimal_separator": ".",
        },
        "columns": columns, "rows": results[:limit],
        "selected_columns": plan["select"], "selected_rows": selected,
        "selected_truncated": bool(plan["select"] and len(matched) > limit),
        "grand_totals": grand_totals,
        "coverage": {"total_rows": len(source_rows), "matched_rows": len(matched),
                     "returned_rows": min(len(results), limit), "total_result_rows": total_result_rows,
                     "complete_input": True},
        "truncated": total_result_rows > limit,
        "provenance": {
            "source_columns": [{"name": name, "column": index} for index, name in enumerate(source_columns, 1) if name in referenced],
            "matched_source_rows": [row["source"]["row"] for row in matched],
            "matched_source_locations": [_location(row["source"]) for row in matched],
            "arithmetic": "Decimal", "precision": PRECISION, "rounding": "ROUND_HALF_EVEN",
            "rounded": rounded, "numeric_missing_policy": "reject_query", "formulas_executed": False,
            "aggregate_scope": "all_matched_rows_after_filters",
        },
        "plan_sha256": _fingerprint(plan),
    }
    encoded = _bounded_result_bytes(result)
    result["result_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result
