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
python3 tests/verify_step10_pdf_wide_table.py  # P0 fix: 13-column table with unique sentinels in every cell, exported to PDF+DOCX, confirms zero silent column/cell loss
python3 tests/verify_step11_language_neutral_completeness.py  # P1 fix: EN/DE/HR parallel fixtures score materially equivalently; real German Golden Artefact Acceptance fixtures re-checked; Croatian fixture confirms the fallback layer isn't German-only
python3 tests/verify_step12_export_payload.py  # JSON/package export testability: single-case export (no download), ZIP manifest, round-trip, multilingual round-trip, legacy import, no duplicate JSON builder
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
in the same delta at once. Run `verify_step10_pdf_wide_table.py` before any
commit touching the PDF `table`/`fitTableWidths`/`drawTableBlock` functions
inside `__eaceV32.buildPdf` — this is the P0 fix for a confirmed defect
(a 13-column table silently lost its last two columns off the printable
page); a regression here re-introduces silent PDF content loss with no
visible symptom short of this test. Run
`verify_step11_language_neutral_completeness.py` before any commit
touching `ARTEFACT_ANATOMY_DIMENSIONS`, `STRUCTURAL_DIMENSION_DETECTORS`,
or `LEXICAL_DIMENSION_FALLBACK` — confirms completeness scoring doesn't
silently regress into English-only detection for any of the languages
this test exercises. Run `verify_step8_field_propagation.py` before
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
reader but this test's exact-string check catches it immediately. Run
`verify_step12_export_payload.py` before any commit touching `jsonPayload`,
`fullJson` (inside `eace-v42-export-runtime`), `exportCentral`'s
`format==='json'` branch (inside `eace-v44-runtime`), `workspacePayload`, or
`importPortfolio` — `jsonPayload` (exposed as
`window.EACEExportService.jsonPayload`) is the one canonical single-case
export payload builder; this test caught two live duplicates of it
(`fullJson`'s old inline `EACE_CASE_EXPORT_V42` shape and `exportCentral`'s
old inline `EACE_CASE_EXPORT_V44` shape) that the actual "Export JSON"
button and "Export ZIP" button resolved to instead of `jsonPayload`, via
the same reassignment-shadowing pattern documented above
(`EACEExportService.exportSystem` gets overwritten in place by a later
script block). Both now delegate to the real canonical builder. This test
also caught that `window.importPortfolio` has the same shadowing problem —
the live, UI-wired assignment (~line 53010) is a *second*, less capable
`importPortfolio` than the earlier bare `function importPortfolio(e){...}`
declaration (~line 6009, dead code): it dropped
`generatedOutputs`/`evidence`/`auditRecords`/`attachments` entirely on a
single-case re-import (they are top-level payload siblings of `system`,
not nested inside it) and never restored workspace-level
`settings`/`organisation` on a whole-workspace re-import at all. A
regression in any of these functions reintroduces silent data loss on
export/import with no visible symptom short of this test's round-trip
checks (Tests C/D/E).
