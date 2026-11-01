# Parser/query review and preservation

Scope: pure toolkit byte parser and query engine. No permission, chat, provider
or browser assertion follows from this report. The tracked historical flow
evidence remains unchanged.

## Independent findings, preserved and corrected before handoff

A separate read-only reviewer reproduced three defects in the first candidate.
The first managed check remains preserved as execution
`395fcd7506ad4e1eaf9feb984d3f7b2e`; its passing tests did not catch these defects.

| Finding | Original observation | Correction | Independent repeat |
|---|---|---|---|
| P1, zero representation growth | A 2,814-byte plan with eight derived columns and 120 expression nodes expanded a zero into 1,000,038 characters before output rejection. One-row JSON reached 2,006,947 bytes. | Canonical zero before formatting; bounded incremental result serialization. | Same query returns `0`, complete JSON 7,943 bytes. Regression asserts exponent/representation bound before formatting. |
| P2, legacy dialect regression | Passing only Sniffer's delimiter lost its quote character and initial-space rules; quoted commas could become extra columns or a valid extraction could fail. | Preserve the complete legacy dialect in shared record decoding; new calculation tables select their strict quoting explicitly. | Both original cases exactly match `csv.reader(..., Sniffer dialect)`, including source columns. |
| P2, ambient Decimal dependence | An inherited Inexact trap turned a valid mean into failure under the caller's context. | Use an explicit Decimal Context, including traps and exponent limits. | Mean result and hashes identical with outer precision 3, Emax 1, Emin −1, Inexact trap and ROUND_DOWN. |

All three findings were closed by the independent reviewer through the same
reproductions. The reviewer ran 83 tests PASS. One additional realistic output
limit regression was then added: a complete bounded CSV whose long headers
would inflate a detail response is rejected with `CSV_OUTPUT_LIMIT`, while its
complete row count remains available. The final focused run has **84 PASS**.

## Final local command

`python -m pytest -q tests/test_csv_query.py tests/document_tools/test_standalone.py`

The managed rerun binds these source/test/evidence files to an execution receipt.
The query engine exposes finite precision and observed rounding; it makes no
claim that a provider interpreted the user's intended calculation correctly.
The host must visibly present the chosen formula/filter and provenance.

The existing `parsers.py` source used CRLF. Its touched file is normalized to LF
so added source lines pass `git diff --check`; code outside the CSV extraction
branch otherwise retains its behavior.
