"""Pure CSV decoding/query checks over exact historical bytes and hostile input.

No model, browser, filesystem authorization or main-chat execution is implied.
Those boundaries are exercised separately by CSV access/flow tests.
"""
from copy import deepcopy
from decimal import Decimal, Inexact, ROUND_DOWN, localcontext
import hashlib
import json
from pathlib import Path
import sys

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/document-toolkit"))
from document_toolkit.core import DocumentError, Limits
from document_toolkit.parsers import parse, parse_csv_table
from document_toolkit.csv_query import CSV_QUERY_TOOL, CsvQueryError, execute_csv_query


HISTORICAL = (
    b"pedido,cliente,producto,unidades,precio_unitario,descuento_pct,estado\n"
    b"P001,Alba,Camiseta,12,18.50,10,pendiente\n"
    b"P002,Bruno,Gorra,6,9.00,0,entregado\n"
    b"P003,Carmen,Taza,8,6.25,5,pendiente\n"
)


def order_plan():
    return {"derive": [{"name": "importe", "expression": {"op": "mul", "args": [
        {"op": "mul", "args": [{"column": "unidades"}, {"column": "precio_unitario"}]},
        {"op": "sub", "args": [{"number": "1"}, {"op": "div", "args": [
            {"column": "descuento_pct"}, {"number": "100"}]}]},
    ]}}], "select": ["pedido", "cliente", "importe"], "group_by": ["estado"],
        "aggregates": [{"op": "sum", "column": "importe", "as": "total"}]}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def test_exact_historical_csv_per_order_group_and_general_totals_with_original_locations():
    assert len(HISTORICAL) == 183
    assert hashlib.sha256(HISTORICAL).hexdigest() == "8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5"
    table, plan = parse_csv_table(HISTORICAL), order_plan()
    original_table, original_plan = deepcopy(table), deepcopy(plan)
    result = execute_csv_query(table, plan)
    assert [Decimal(row["values"]["importe"]) for row in result["selected_rows"]] == [Decimal("199.80"), Decimal("54.00"), Decimal("47.50")]
    assert [(row["values"]["estado"], Decimal(row["values"]["total"])) for row in result["rows"]] == [("pendiente", Decimal("247.30")), ("entregado", Decimal("54.00"))]
    assert Decimal(result["grand_totals"]["values"]["total"]) == Decimal("301.30")
    assert result["grand_totals"]["scope"] == "all_matched_rows_after_filters"
    assert result["rows"][0]["source_rows"] == [2, 4]
    assert result["rows"][0]["source_locations"] == [{"row": 2, "start_line": 2, "end_line": 2}, {"row": 4, "start_line": 4, "end_line": 4}]
    assert result["provenance"]["source_columns"] == [{"name": column, "column": number} for number, column in enumerate(table["columns"], 1) if column != "producto"]
    assert result["coverage"] == {"total_rows": 3, "matched_rows": 3, "returned_rows": 2, "total_result_rows": 2, "complete_input": True}
    assert not result["provenance"]["rounded"] and not result["truncated"]
    assert table == original_table and plan == original_plan
    assert "unidades" in result["interpretation"]["derived"][0]["text"]
    assert result["plan_sha256"] == hashlib.sha256(canonical(result["plan"])).hexdigest()
    fingerprint = result.pop("result_sha256")
    assert fingerprint == hashlib.sha256(canonical(result)).hexdigest()


def test_filters_make_grand_total_explicitly_filtered_and_never_extrapolate_display_limit():
    plan = order_plan()
    plan.update(filters=[{"column": "estado", "op": "eq", "value": "pendiente"}], limit=1)
    result = execute_csv_query(parse_csv_table(HISTORICAL), plan)
    assert Decimal(result["grand_totals"]["values"]["total"]) == Decimal("247.30")
    assert result["provenance"]["matched_source_rows"] == [2, 4]
    assert result["coverage"]["matched_rows"] == 2
    assert len(result["selected_rows"]) == 1 and result["selected_truncated"]
    assert not result["truncated"]  # one group is complete despite detail limit


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_explicit_and_detected_dialects_preserve_utf8_bom_empty_cells_and_formulas(delimiter):
    data = ("\ufeffname" + delimiter + "value\r\nÁlba" + delimiter + "\r\nLiteral" + delimiter + "=2+2\r\n").encode()
    for selection in (delimiter, "auto"):
        table = parse_csv_table(data, delimiter=selection)
        assert table["delimiter"] == delimiter
        assert table["rows"][0]["cells"] == ["Álba", ""]
        assert table["rows"][1]["cells"] == ["Literal", "=2+2"]
        answer = execute_csv_query(table, {"select": ["name", "value"]})
        assert answer["rows"][1]["values"]["value"] == "=2+2"
        assert answer["provenance"]["formulas_executed"] is False


def test_quoted_delimiters_quotes_newlines_and_original_physical_locations():
    table = parse_csv_table(b'name,value\n"A, ""B""\nC",3\nD,4\n')
    assert table["rows"][0] == {"row": 2, "start_line": 2, "end_line": 3, "cells": ['A, "B"\nC', "3"]}
    assert table["rows"][1]["start_line"] == 4
    assert table["total_lines"] == 4
    result = execute_csv_query(table, {"select": ["name"]})
    assert result["rows"][0]["source_locations"][0]["end_line"] == 3


@pytest.mark.parametrize("raw,code", [
    (b'a,b\n"unterminated,2\n', "CSV_MALFORMED"),
    (b'a,b\n1"broken,2\n', "CSV_MALFORMED"),
    (b'a,b\n"one"junk,2\n', "CSV_MALFORMED"),
    (b'a,b\n1,2,3\n', "CSV_MALFORMED"),
    (b'a,b\n\n1,2\n', "CSV_MALFORMED"),
    (b'a,a\n1,2\n', "CSV_HEADER_DUPLICATE"),
    (b'a, A \n1,2\n', "CSV_HEADER_DUPLICATE"),
    (b',a\n1,2\n', "CSV_HEADER_INVALID"),
    (b'', "CSV_EMPTY_OR_BINARY"),
    (b'a\n\x00\n', "CSV_EMPTY_OR_BINARY"),
    (b'a\n\xff\n', "CSV_NOT_UTF8"),
    (b'\xff\xfea\x00', "CSV_NOT_UTF8"),
    (b'a|b,c\n1|2,3\n', "CSV_DELIMITER_AMBIGUOUS"),
])
def test_malformed_csv_and_ambiguous_structure_are_never_silently_repaired(raw, code):
    with pytest.raises(DocumentError) as error:
        parse_csv_table(raw)
    assert error.value.code == code


def test_explicit_separator_resolves_structural_ambiguity_without_guessing():
    raw = b'a|b,c\n1|2,3\n'
    assert parse_csv_table(raw, delimiter="|")["columns"] == ["a", "b,c"]
    assert parse_csv_table(raw, delimiter=",")["columns"] == ["a|b", "c"]


@pytest.mark.parametrize("raw,options,code", [
    (b'a\n' + b'1\n' * 250, {}, "CSV_ROW_LIMIT"),
    (b'a,b\n1,2\n3,4\n', {"max_rows": 2}, "CSV_ROW_LIMIT"),
    (b'a,b\n1,2\n', {"max_columns": 1}, "CSV_COLUMN_LIMIT"),
    (b'a,b\n1,2\n', {"max_cells": 3}, "CSV_CELL_LIMIT"),
    (b'a\n' + b'x' * (256 * 1024), {}, "CSV_BYTE_LIMIT"),
    (b'a\n1\n', {"delimiter": ":"}, "CSV_DELIMITER_INVALID"),
    (b'a\n1\n', {"max_rows": 251}, "CSV_INVALID_LIMIT"),
    (b'a\n1\n', {"max_rows": True}, "CSV_INVALID_LIMIT"),
], ids=["default-row-limit", "explicit-row-limit", "column-limit", "cell-limit",
       "byte-limit", "invalid-delimiter", "excessive-row-limit", "boolean-row-limit"])
def test_limits_do_not_turn_a_partial_or_wide_file_into_single_column_success(raw, options, code):
    with pytest.raises(DocumentError) as error:
        parse_csv_table(raw, **options)
    assert error.value.code == code


def test_shared_record_decoder_preserves_existing_document_extraction_dialects():
    result = parse(b'name;value\n"a;b";=2+2\n', ".csv", Limits())
    assert result["segments"] == [
        {"text": "name", "location": {"row": 1, "column": 1}},
        {"text": "value", "location": {"row": 1, "column": 2}},
        {"text": "a;b", "location": {"row": 2, "column": 1}},
        {"text": "=2+2", "location": {"row": 2, "column": 2}},
    ]
    for data, expected in [(b"name,value\n'a,b',2\n", ["name", "value", "a,b", "2"]),
                           (b'name, value\nA, "B,C"\n', ["name", "value", "A", "B,C"])]:
        observed = parse(data, ".csv", Limits())
        assert [item["text"] for item in observed["segments"]] == expected
        assert observed["segments"][-1]["location"] == {"row": 2, "column": 2}
    # Existing extraction remains permissive; the new calculation table must
    # reject malformed quotes even when extraction previously rendered them.
    with pytest.raises(DocumentError, match="CSV_MALFORMED_QUOTES"):
        parse_csv_table(b'a,b\n1"bad,2\n', delimiter=",")


@pytest.mark.parametrize("raw", ["", "NaN", "Infinity", "-Infinity", "1,234", "1 234", "1e3", " 1", "1 ", "€2", "10%", "=2+2", "True", "1_000", ".5"])
def test_numeric_interpretation_never_coerces_blanks_formulas_groupings_or_nonfinite_values(raw):
    table = parse_csv_table(('name;value\nitem;' + raw + '\n').encode(), delimiter=";")
    with pytest.raises(CsvQueryError, match="CSV_NUMERIC_FORMAT"):
        execute_csv_query(table, {"aggregates": [{"op": "sum", "column": "value", "as": "total"}]})


def test_explicit_comma_decimal_and_dot_constants_with_exact_numeric_filters():
    table = parse_csv_table(b'name;value\na;1,25\nb;2,50\n')
    plan = {"derive": [{"name": "twice", "expression": {"op": "mul", "args": [{"column": "value"}, {"number": "2.0"}]}}],
            "filters": [{"column": "value", "op": "gte", "value": "2,00"}],
            "select": ["name", "twice"], "aggregates": [{"op": "sum", "column": "twice", "as": "total"}]}
    result = execute_csv_query(table, plan, decimal_separator=",")
    assert Decimal(result["rows"][0]["values"]["total"]) == Decimal("5.00")
    assert result["provenance"]["matched_source_rows"] == [3]
    assert result["interpretation"]["constant_decimal_separator"] == "."


def test_empty_selection_has_count_zero_sum_zero_and_explicit_undefined_mean():
    result = execute_csv_query(parse_csv_table(HISTORICAL), {
        "filters": [{"column": "cliente", "op": "eq", "value": "absent"}],
        "aggregates": [{"op": "count", "as": "count"}, {"op": "sum", "column": "unidades", "as": "sum"},
                       {"op": "mean", "column": "unidades", "as": "mean"}]})
    assert result["rows"][0] == {"values": {"count": "0", "sum": "0", "mean": None}, "source_rows": [], "source_locations": []}
    assert result["coverage"]["matched_rows"] == 0


def test_header_only_is_a_complete_empty_dataset():
    result = execute_csv_query(parse_csv_table(b'name,value\n'), {"aggregates": [{"op": "count", "as": "rows"}]})
    assert result["coverage"]["complete_input"] and result["coverage"]["total_rows"] == 0
    assert result["rows"][0]["values"] == {"rows": "0"}


def test_grouped_totals_are_complete_even_when_group_presentation_is_capped():
    result = execute_csv_query(parse_csv_table(HISTORICAL), {
        "group_by": ["cliente"], "aggregates": [{"op": "sum", "column": "unidades", "as": "count"}], "limit": 1})
    assert result["truncated"] and result["coverage"]["total_result_rows"] == 3
    assert result["grand_totals"]["values"]["count"] == "26"
    assert result["grand_totals"]["source_rows"] == [2, 3, 4]


def test_decimal_rounding_is_disclosed_and_binary_float_error_is_absent():
    table = parse_csv_table(b'value\n0.1\n0.2\n0.2\n')
    result = execute_csv_query(table, {"aggregates": [
        {"op": "sum", "column": "value", "as": "sum"}, {"op": "mean", "column": "value", "as": "mean"}]})
    assert result["rows"][0]["values"]["sum"] == "0.5"
    assert result["provenance"]["rounded"] and result["provenance"]["precision"] == 38


def test_query_does_not_inherit_caller_decimal_traps_rounding_or_exponent_limits():
    table = parse_csv_table(b'value\n1\n2\n2\n')
    plan = {"aggregates": [{"op": "mean", "column": "value", "as": "mean"}]}
    expected = execute_csv_query(table, plan)
    with localcontext() as outer:
        outer.traps[Inexact] = True
        outer.prec = 3
        outer.Emax, outer.Emin = 1, -1
        outer.rounding = ROUND_DOWN
        assert execute_csv_query(table, plan) == expected


def test_zero_exponent_cannot_expand_into_megabytes_before_output_limit(monkeypatch):
    from document_toolkit import csv_query

    def product(expressions):
        if len(expressions) == 1:
            return expressions[0]
        middle = len(expressions) // 2
        return {"op": "mul", "args": [product(expressions[:middle]), product(expressions[middle:])]}

    derives, previous = [], "v"
    for index in range(8):
        name = f"x{index}"
        derives.append({"name": name, "expression": product([{"column": previous} for _ in range(8)])})
        previous = name
    observed = []
    original_display = csv_query._display

    def check_before_allocating(value):
        if isinstance(value, Decimal):
            # The adversarial case used to reach ~one million fractional zero
            # digits here; check its representation before formatting anything.
            assert abs(value.as_tuple().exponent) <= 100
        rendered = original_display(value)
        if isinstance(rendered, str):
            assert len(rendered) < 100
        observed.append(rendered)
        return rendered

    monkeypatch.setattr(csv_query, "_display", check_before_allocating)
    result = execute_csv_query(parse_csv_table(b'v\n0.00000000000000000000000\n'), {"derive": derives, "select": [previous]})
    assert result["rows"][0]["values"] == {previous: "0"}
    assert len(canonical(result)) < 20000 and observed


@pytest.mark.parametrize("plan,code", [
    ({}, "CSV_QUERY_EMPTY"),
    ({"select": ["invented"]}, "CSV_UNKNOWN_COLUMN"),
    ({"select": ["pedido"], "path": "/etc/passwd"}, "CSV_QUERY_INVALID"),
    ({"select": ["pedido", "pedido"]}, "CSV_QUERY_INVALID"),
    ({"select": ["pedido"], "limit": True}, "CSV_QUERY_LIMIT"),
    ({"select": ["pedido"], "limit": 101}, "CSV_QUERY_LIMIT"),
    ({"select": ["pedido"], "group_by": ["estado"]}, "CSV_AGGREGATE_REQUIRED"),
    ({"aggregates": [{"op": "count", "column": "pedido", "as": "n"}]}, "CSV_AGGREGATE_INVALID"),
    ({"aggregates": [{"op": "median", "column": "unidades", "as": "n"}]}, "CSV_AGGREGATE_INVALID"),
    ({"aggregates": [{"op": "sum", "as": "n"}]}, "CSV_AGGREGATE_INVALID"),
    ({"aggregates": [{"op": "count", "as": "n"}, {"op": "count", "as": "N"}]}, "CSV_COLUMN_COLLISION"),
    ({"select": ["pedido"], "filters": [{"column": "pedido", "op": "contains", "value": "P"}]}, "CSV_FILTER_INVALID"),
    ({"select": ["pedido"], "filters": [{"column": "unidades", "op": "gt", "value": 3}]}, "CSV_FILTER_INVALID"),
    ({"select": ["pedido"], "derive": [{"name": "cliente", "expression": {"number": "1"}}]}, "CSV_COLUMN_COLLISION"),
    ({"select": ["pedido"], "derive": [{"name": "x", "expression": {"python": "__import__('os').system('x')"}}]}, "CSV_EXPRESSION_INVALID"),
    ({"select": ["pedido"], "derive": [{"name": "x", "expression": {"op": "pow", "args": [{"number": "2"}, {"number": "9"}]}}]}, "CSV_EXPRESSION_INVALID"),
    ({"select": ["pedido"], "derive": [{"name": "x", "expression": {"op": "div", "args": [{"number": "1"}, {"number": "0"}]}}]}, "CSV_DIVISION_BY_ZERO"),
    ({"select": ["pedido"], "derive": [{"name": "x", "expression": {"column": "x"}}]}, "CSV_UNKNOWN_COLUMN"),
])
def test_invalid_or_unsupported_plan_is_rejected_instead_of_returning_an_invented_answer(plan, code):
    with pytest.raises(CsvQueryError) as error:
        execute_csv_query(parse_csv_table(HISTORICAL), plan)
    assert error.value.code == code


def test_expression_complexity_and_numeric_magnitude_are_bounded():
    expression = {"number": "1"}
    for _ in range(10):
        expression = {"op": "add", "args": [expression, {"number": "1"}]}
    with pytest.raises(CsvQueryError, match="CSV_QUERY_LIMIT"):
        execute_csv_query(parse_csv_table(HISTORICAL), {"select": ["pedido"], "derive": [{"name": "x", "expression": expression}]})
    expression = {"op": "mul", "args": [{"number": "999999999999999999999999"}, {"number": "999999999999999999999999"}]}
    with pytest.raises(CsvQueryError, match="CSV_NUMERIC_LIMIT"):
        execute_csv_query(parse_csv_table(HISTORICAL), {"select": ["pedido"], "derive": [{"name": "x", "expression": expression}]})


def test_invalid_table_or_source_row_metadata_cannot_fabricate_provenance():
    table = parse_csv_table(HISTORICAL)
    table["rows"][0]["row"] = 999
    with pytest.raises(CsvQueryError, match="CSV_TABLE_INVALID"):
        execute_csv_query(table, {"select": ["pedido"]})


def test_large_repeated_header_output_is_bounded_but_complete_count_remains_available():
    columns = [f"column_{index}_" + "x" * 185 for index in range(64)]
    raw = (",".join(columns) + "\n" + (",".join(["1"] * 64) + "\n") * 50).encode()
    table = parse_csv_table(raw)
    with pytest.raises(CsvQueryError, match="CSV_OUTPUT_LIMIT"):
        execute_csv_query(table, {"select": columns})
    count = execute_csv_query(table, {"aggregates": [{"op": "count", "as": "rows"}]})
    assert count["rows"][0]["values"]["rows"] == "50"
    assert count["coverage"]["complete_input"]


def test_tool_schema_accepts_the_same_historical_query_and_contains_no_file_or_code_effect():
    parameters = CSV_QUERY_TOOL["function"]["parameters"]
    jsonschema.Draft202012Validator.check_schema(parameters)
    jsonschema.Draft202012Validator(parameters).validate(order_plan())
    assert CSV_QUERY_TOOL["function"]["name"] == "query_csv"
    assert not {"path", "code", "command", "filename"}.intersection(parameters["properties"])
