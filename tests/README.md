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
python3 tests/verify_step3_engine_authored_specs.py  # the 8 Step 0 gaps now RESOLVED with real content, incl. all 7 contractual instruments
python3 tests/verify_step4_completeness_validator.py  # 5-state deterministic completeness classifier, all states + taxonomy consistency
python3 tests/verify_step5_source_governance_and_enrichment.py  # source-status labels, NB hierarchy, empty-annex rule, Vulnerability column, Step 3B targeting
python3 tests/verify_step6_readiness_and_reassessment.py  # extractUnresolvedFields, computeReadinessState (8-state ladder + 6 dimensions), classifyReassessmentDelta (4-class precedence)
python3 tests/verify_step7_language_propagation.py  # language-exemption clauses on the new closed-vocabulary labels; languageDirective precedes all new prompt sections, incl. a non-English authLang case
python3 tests/verify_step8_field_propagation.py  # every Master Profile / Organisation Profile field ID actually reaches buildIntakeContext's generation-context output (214/214 system fields, 26/26 org fields, live-tested)
python3 tests/verify_step9_executive_decision_layer.py  # Executive Dashboard's 3 new columns (Readiness State/Operational Result/Artefact Completeness) present for major artefacts, absent for CSV/P1-brief, vocabulary matches READINESS_LADDER/assessArtefactCompleteness exactly
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
export. Run `verify_step6_readiness_and_reassessment.py` before any commit
touching `extractUnresolvedFields`, `computeReadinessState`, or
`classifyReassessmentDelta` — these are pure/deterministic functions (no
generation, no API cost) built on top of Step 4's
`assessArtefactCompleteness`; the test confirms `ARTEFACT_STATUS` inside
the readiness ladder never drifts from the Step 4 verdict for the same
text, that external readiness facts (approved/executed/superseded) can
only ever advance the ladder and that `superseded` is terminal, and that
the reassessment classifier's 4-class precedence
(CLASSIFICATION_RELEVANT_CHANGE > MATERIAL_FACT_CHANGE > NEW_EVIDENCE_ONLY
> DOCUMENT_COMPLETION_ONLY) holds even when multiple signals are present
in the same delta at once. Run `verify_step8_field_propagation.py` before
any commit touching `buildIntakeContext`, `ORG_FALLBACK_COMPOSERS`, or
`applyOrgLiveFallback` — this is the field-propagation regression: it
enumerates every field ID from `MASTER_GROUPS`/`MASTER_GROUPS_EXT2` (the
Engine Hub intake form), `FIELD_SCHEMA` (the System Workspace "Master
Profile" tab), and `ORG_PROFILE_SCHEMA` (the Organisation Profile), sets a
unique value per field on an isolated synthetic system, and confirms it
actually reaches the assembled "SYSTEM PROFILE — USER-SUPPLIED INPUT"
prompt text via `getExecutionInputData()`/`buildIntakeContext` — i.e. it
tests generation-context resolution, not just whether a field renders in a
UI form. This test caught (and this session's commit fixed) ~130 fields
that were captured by one of the two live intake screens but silently
never reached generation, including several same-fact-different-field-ID
collisions (`sysDesc`/`sysDescription`, `countryDeploy`/
`deploymentCountries`, `provName`/`orgName`, `nis2Provider`/
`nisEntityProvider`, and others) where a user could fill in the "Master
Profile" tab and see nothing change in a generated document. A regression
here silently re-orphans user-supplied facts without any error or visible
symptom short of this test. Run `verify_step9_executive_decision_layer.py`
before any commit touching the Executive Dashboard section of
`structuredArtefactFormat` (inside `buildSystemPrompt`) or the
`READINESS_LADDER`/`assessArtefactCompleteness` vocabularies — this test
is the tripwire for prompt-vs-engine vocabulary drift: if either constant
changes without updating the other, the mismatch is silent to a human
reader but this test's exact-string check catches it immediately.
