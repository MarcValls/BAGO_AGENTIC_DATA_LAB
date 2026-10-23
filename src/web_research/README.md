# Public Web Research SDK

Pure Python standard library; no ADL/server, model provider or browser dependency.

Explicit CLI authorization (HTTPS origin, one invocation, fresh data directory):

```
python core.py --store C:/test-data/web-captures --allow-origin https://www.sollutia.com https://www.sollutia.com/es/empresa.html
```

`--allow-origin` expresses caller authorization for that public origin. This CLI
cannot consume ADL conversation grants; ADL grants remain bound to owner, conversation
and current revision, expire after300seconds, and are consumed once before the turn.
Pending grants are memory-only and invalid after coordinator restart (fail closed).
SDK users explicitly issue/consume `Authorizations` before constructing a reader.

Limits: eight page tool attempts per chat turn; at most eight successful request
claims per permit, three redirects per page (at most32 HTTP requests), 1MiB body,
24,000 extracted text characters, 20-second read deadline and bounded socket waits.
DNS uses the OS resolver in a daemon thread; the caller waits at most3seconds.
That OS resolver cannot be forcibly stopped, and never starts HTTP work after the
wait expires. This is not a sandbox for other host processes or code.

Each redirect must remain on an authorized origin, HTTPS port443. DNS with any
non-global address is denied. The TCP connection uses the validated IP directly;
TLS validates the original hostname. System HTTP proxies, cookies and credentials
are not used. The reader does not execute scripts or load subresources. It accepts
only HTML/XHTML/plain text, requests identity encoding and honors the declared
charset with strict decoding (UTF8 if absent). Sensitive credential query keys
and userinfo are rejected; this is not a universal detector of private URL data.

Snapshots contain `raw.bin`, UTF8 `text.txt` and `capture.json`. Only after writes,
fsync and revalidation does a source become ALLOW. Partial failures remain failure;
partial directories can be inspected but are not returned as successful captures.
`SnapshotStore(root).load(snapshot_id, expected_manifest_sha256)` revalidates both
raw/text hashes and the supplied manifest identity. Do not omit the expected
manifest hash when checking a previously recorded source. Snapshot paths use
opaque IDs and are not local file read grants for the agent.

Source text is untrusted data, including visible prompt-injection instructions.
The tool marks it untrusted and the host prompt instructs the model accordingly;
that is not proof that every model will obey or that any answer is factually sound.
Claims must still be checked against the recorded source and task acceptance.
A model response without a successful read produces no fabricated source.

LocalTrace events use `web.read`, authorization IDs and snapshot references.
Exporter acceptance alone does not demonstrate Jaeger query/correlation; the host
must show that observation separately. This SDK does not claim to have performed
inference, business analysis, authorized messaging or delivery.

SW04 repair: an absolute watchdog closes registered TCP/TLS sockets on deadline,
including request transmission, status line, headers and body. TLS handshake is
explicit so its socket is registered before it can block. Header/body file reads
also check the same deadline. Timed-out reads do not leave an HTTP worker capable
of further requests; an OS DNS resolver may still finish without starting HTTP.
