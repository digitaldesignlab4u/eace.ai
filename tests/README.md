# Tests

No formal test framework — these are headless-browser scripts against the
live app, since `index.html` has no build step to hook a real test runner
into. See `CLAUDE.md` at the repo root for why this matters (the
reassignment-shadowing gotcha means reading the source isn't sufficient
evidence that a fix works).

## Running

```bash
python3 -m http.server 8899 &            # serve the repo root
python3 tests/regression.py              # app's built-in classification self-test, expect 10/10
python3 tests/verify_build_info.py       # BUILD_INFO + isSyntheticCase propagation, all real export paths
python3 tests/verify_canonical_mapping.py  # P2A/P2B canonical anchor resolution, expect 53/53
python3 tests/verify_mapping_safeguard.py  # CANONICAL SPEC MAPPING FAILURE blocking-error path
python3 tests/verify_step1_contract.py     # operational artefact completeness contract (P2A/P2B/P3/P4 only, not P1/CSV)
python3 tests/verify_step2_p0_enrichment.py  # P0 Human Oversight (P2A O08, P2B O09) + FRIA matrix (P2B O06) targeting
```

All need Playwright with a Chromium binary available (see
`CHROMIUM_PATH` at the top of each script — adjust if your environment's
binary lives elsewhere). All exit non-zero on any failed check or page
error, so they're safe to chain with `&&` before a commit/push.

Run `regression.py` before any commit touching classification, routing,
or shared workspace state. Run `verify_build_info.py` before any commit
touching BUILD_INFO, `isSyntheticCase`, or the export pipeline
(`__eaceV32`/`__eaceV42`/`__eaceV44`, `exportSystemJSON`,
`buildSingleOutputDocxBlob`). Run `verify_canonical_mapping.py` and
`verify_mapping_safeguard.py` before any commit touching
`extractCanonicalOutputBlock`, `OUTPUT_CANONICAL_ANCHORS`, or
`buildOutputRegistry` — these are the P2A/P2B canonical-spec routing layer
documented in the Step 0 audit finding (see git log), and a regression
here silently degrades every downstream P2A/P2B output back to the
front-matter-status-board mismatch that fix corrected. Note the three-state
contract `verify_mapping_safeguard.py` checks — RESOLVED /
MAPPING_FAILURE / NO_DEDICATED_SECTION are NOT interchangeable:
MAPPING_FAILURE blocks generation of that one output only (never the rest
of the pillar's registry — see its "isolation" check); NO_DEDICATED_SECTION
never blocks anything and must never read as licence for the model to
invent the missing methodology. Run `verify_step1_contract.py` before any
commit touching `buildSystemPrompt` or the artefact-type detection
heuristic inside it — confirms the completeness contract stays scoped to
P2A/P2B/P3/P4 non-CSV outputs and never leaks into P1 or a machine-readable
export.
