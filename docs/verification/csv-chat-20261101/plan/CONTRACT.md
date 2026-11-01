# CSV main-chat integration contract

Base: `16b74a590889d6b42d7889abc8cd114b35c5dbf1`. PR #112 is merged.
This scope implements the user's CSV mission; it does not implement another
Decision Inspector. The existing team protocol coordinates disjoint work scopes.
The tracked legacy team runtime remains byte-for-byte preserved. This task uses
the controller's supported `--root` option at the checkout's parent directory.

## User path and HTTP transport

Main chat → Resources → Consultar archivo → CSV del proyecto. The selector uses
the existing project-permissions directory metadata API, never a content preview.
Text/Markdown retains its existing KnowledgeIngest route. The CSV is neither
imported nor indexed, and no document-corpus grant is issued.

`csv_read = {path, delimiter, decimal_separator}` where path is project-relative,
delimiter is `auto`, comma, semicolon, tab or pipe, and decimal_separator is dot or
comma (explicit UI choice; default dot). One CSV per request.

1. POST `/api/workspace-read/authorizations` with existing owner_kind, owner_id,
   conversation_id, revision, paths=[path], plus
   `csv_request: {message, csv_read}` and `expected_project: {project_id, binding,
   revision}` from the current metadata snapshot. This binds the exact question,
   parse options, file metadata, project identity and saved READ policy revision.
2. POST `/api/chat/control` with operation=chat, message, conversation_id, revision,
   workspace_read_authorization_id and the identical csv_read object.
3. The server consumes the existing grant once, rechecks project policy and STOP,
   reads one bounded immutable byte snapshot, parses via the shipped toolkit,
   obtains a strictly validated query plan from the selected provider, calculates
   with Decimal, and persists the answer with sources/read_events/csv_analysis.
4. Every new question needs a new grant. CSV selection and consent reset when
   project, conversation, revision or owner changes. A saved project READ policy
   never expands the exact selected CSV scope. No web or document grants are
   inherited by this submission. The normal unsent chat draft is preserved.

`DELETE /api/workspace-read/authorizations/{token}` with owner_kind, owner_id,
conversation_id, revision revokes only that matching existing grant, including a
consumed but still active CSV request. Cancellation is idempotent. No new grant
registry is introduced.

## Parsing and calculation module interface (W03)

The existing document toolkit owns the byte parser. Add
`parse_csv_table(data, *, delimiter='auto', max_rows=250, max_columns=128,
max_cells=32000)` in its parsers module, returning:

`{columns: [str], rows: [{row: 2, start_line: 2, end_line: 2, cells: [str]}],
delimiter: str, total_lines: int}`. Row numbers include the header as row 1.
Preserve empty cells, literal formulas and source locations. Reject malformed
quoting, uneven width, blank/duplicate headers, ambiguous delimiter and limits.
The chat supplies only UTF-8/UTF-8 BOM and never a truncated snapshot. Existing
toolkit CSV extraction should reuse the shared parser primitives where compatible.

`document_toolkit.csv_query` exports `CSV_QUERY_TOOL` (function `query_csv`),
`CsvQueryError` with `.code`, and
`execute_csv_query(table, plan, *, decimal_separator='.') -> dict`.

Plan fields: select=[column names], derive=[{name, expression}],
filters=[{column, op, value}], group_by=[columns],
aggregates=[{op, column?, as}], limit (max 100).
Expressions: {column}, {number: decimal string}, or
{op: add|sub|mul|div, args: [expression, expression]}.
Filter operations eq/ne compare literal text; gt/gte/lt/lte compare strictly
parsed Decimal values. Aggregates: count, sum, min, max, mean. Unknown keys,
columns or operators, empty/nonfinite/ambiguous numerics, zero division,
excessive complexity and output limits fail closed. No eval/exec, commands,
spreadsheet formulas or additional file access. A plan must select or aggregate.

Result includes original plan/interpretation, result columns/rows (Decimal values
as strings), matched source rows/locations, coverage counts, truncation flag for
presentation only, and calculation provenance. Full bounded data determines all
aggregates; a displayed subset is never extrapolated to a total.

Provider interpretation is a proposal, not proven user intent. The answer visibly
states the chosen formula/filter and exact results; absent/invalid/unsupported
plans produce an explicit interpretation error, never a fabricated analysis.
The provider receives untrusted structured data and no file/effect tools.

## Access, revocation and STOP (W02)

Reuse WorkspaceReadAuthorizations, SandboxFilesystem and ProjectPermissions.
Both exact-file grant and current saved READ are mandatory for this CSV route.
Recheck owner/conversation/revision, root/project/binding/policy revision, TTL,
single consumption, revocation and STOP before IO and after interpretation before
publishing data. Metadata selection is not a content read. Enforce the existing
256 KiB and 250 physical-line boundaries without partial aggregate results.
Detect in-place changes as well as replacement before/during/after IO and reject
changes between authorization and use. Final output is bound to file SHA-256,
query plan SHA-256 and result SHA-256. Files remain unchanged by the operation.

Read the existing persistent teamctl STOP authority through the fixed shipped
controller (delivery_review pattern), never executable workspace code. PAUSED or
invalid existing state denies the route; an absent mission does not create one.
Do not claim STOP is globally integrated across other ADL chat flows.

## Verification and evidence

Preserve `docs/verification/user-demand-20261101/**` exactly. New F10/F11/F12
reproductions use the original 183-byte CSV with SHA-256
`8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5`.
Expected row totals: 199.80, 54.00, 47.50; pending 247.30; overall 301.30.
Actual HTTP/handler tests use real filesystem, policy/grants and conversation
storage with a clearly labelled controlled provider interpretation. UI tests
prove dispatch, not live backend/provider operation. Table/Text checks are
preservation tests, never substitutes for chat reading evidence.
Windows, live provider and any unavailable browser checks remain NOT_RUN.
