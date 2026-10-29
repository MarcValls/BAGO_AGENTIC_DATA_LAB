# Reproduce the source-dialog check

Extract `fixture-project.zip` into a disposable folder. Its fixture-project contains the exact synthetic source used in the desktop observation. It is test input copied by the host for reproducibility, not a claim that ADL created it.

1. Use a disposable project copy and select its folder as the ADL workspace. Keep a provider/model configured through the existing product settings; no credentials are supplied by this evidence package.
2. Put an unsent marker in the main chat composer.
3. Open Resources > Consult file and choose `documents/records.txt` relative to that disposable project.
4. Ask for the case identifier and the number of documents without incidents. The source says 13 reviewed, 5 with incidents, and 8 without; the identifier is PROVA-F35BBA3598FB.
5. Submit once. The recorded desktop observation saw one knowledge request, zero chat requests, no URL change, and a cited Codex/gpt-6-luna answer. A future model response is not guaranteed to be byte-identical.
6. Press Escape and check that Resources regains focus and the unsent draft remains unchanged.

Expected source SHA-256: `d6734b202db34d99a28bd274f8105ab412b4d504f33133bd208c27ae4a1fcc7b`.

Run only in an isolated index/data root when reproducing this bounded observation. This repair does not establish cross-project/source isolation for a previously populated shared RAG index. Provider usage follows the user's existing authorization and may incur costs; the evidence package itself makes no model calls.
