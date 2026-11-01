# Bounded CSV query result

`document_toolkit.csv_query.execute_csv_query(table, plan, decimal_separator=...)`
returns `csv-query.result.v1`. This pure function does not read files, authorize
anything, contact a provider or constitute a main-chat verification.

- `plan`: validated copy with explicit defaults; expressions are binary and
  constants always use a dot. Source numeric cells use the user's decimal choice.
- `interpretation`: derived expression trees and readable expressions, exact
  filters, grouping, aggregate specifications and decimal conventions.
- `columns`/`rows`: grouped aggregates when requested; otherwise selected rows.
  Every row has `values`, `source_rows` and physical `source_locations`.
- `selected_columns`/`selected_rows`: selected detail, including alongside totals.
- `grand_totals`: the same aggregate specs over all **matched** rows when grouped;
  its explicit scope is `all_matched_rows_after_filters`, never an unfiltered
  whole-file total after a filter. It carries all contributing source locations.
- `coverage`: complete bounded input, total/matched rows and returned/total result
  rows. `limit` truncates presentation, never arithmetic input.
- `truncated` and `selected_truncated`: independent presentation flags.
- `provenance`: source column indices and locations, arithmetic/precision/rounding,
  rounding observed, strict numeric-missing policy, and formulas_executed=false.
- `plan_sha256`: canonical JSON hash of the normalized plan.
- `result_sha256`: canonical JSON hash of the result **before** adding that hash.
  Canonical JSON is sorted, UTF-8, compact, ensure_ascii=false, allow_nan=false.

Values are text, with computed Decimal values serialized without exponent
notation. Null min/max/mean over an empty match set means undefined, not zero.
Count is the number of rows; sum of an empty set is zero. Numeric operations
reject blanks, grouping marks, exponents, currency/percent signs and formula text.
Numeric equality filters are deliberately not inferred: eq/ne compare literal
strings; gt/gte/lt/lte use the selected decimal convention. Derived values retain
Decimal trailing zeros, except zero is canonicalized before rendering to prevent
representation expansion. Division and mean use an explicit independent Decimal
Context with precision 38, ROUND_HALF_EVEN;
`provenance.rounded` must be displayed if set. No financial rounding is invented.

## Historical exact oracle

`pedidos-original.csv` reproduces the 183 bytes of F10-F12, SHA-256
8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5.
`historical_query.json` and `HISTORICAL_RESULT.json` exercise the real parser and
query engine: per-row 199.80/54.00/47.50, pending 247.30, overall 301.30.
No original historical evidence was edited. Main chat, provider interpretation,
UI and Windows verification are separate gates.
