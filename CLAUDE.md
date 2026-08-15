# EACE — Local-First EU AI Act Compliance Engine

This repo is a single file: `index.html` (~5 MB). No build step, no bundler,
no package.json for the app itself — everything (HTML, CSS, and ~40 inline
`<script>` blocks) lives in that one file, loaded directly in a browser.
Treat any change as a change to *the* file; there is nothing else to sync.

For the full technical/regulatory architecture (deployment model, model
routing, evidence/export design, validation methodology), see the
standalone document **EAI-DD-001 — Technical & Regulatory Architecture**
(not in this repo — it's a separate DD deliverable). This file is the
narrower, code-level companion: rules an agent editing `index.html` needs
that aren't visible from reading any single function in isolation.

## What EACE is

A local-first, BYOK (bring-your-own-key) compliance operating system for
the EU AI Act. It classifies an AI system (P1) and, depending on the
result, routes it into up to four downstream regulatory engines:

- **P1** — Classification (territorial scope, Art. 5 prohibited-practice
  gate, Annex III, risk class). Routing-controlling: P2A/P2B/P3/P4 stay
  `undetermined` until a completed, validated P1 result exists — never
  guessed from sector or provisional data.
- **P2A** — Provider (high-risk) obligations. Routed to the larger model
  in the configured family; smaller models are documented as liable to
  truncate its more complex outputs (Annex IV, QMS).
- **P2B** — Deployer (high-risk) obligations (Art. 26, DPIA, FRIA, NIS2).
- **P3** — Transparency (Art. 50 notices, GPAI disclosure).
- **P4** — Minimal-risk confirmation and residual obligations.

Inference is dispatched directly from the browser to the configured model
provider (currently Anthropic's Messages API) — enforced by the page's
Content-Security-Policy, not just by convention. There is no
EACE-operated backend for the core workflow. Do not describe this as "no
API calls" — it's BYOK, not offline; get the distinction right in any
copy you write.

## The one gotcha that will burn you: reassignment shadowing

This file has ~10 years of accumulated patch generations, visible as
`eace-vNN-*` script-block IDs (v4 through v64+) and object names
(`__eaceV30`, `__eaceV32`, `__eaceV42`, `__eaceV47`...). Many of these
**reassign the same function name** as a later, wrapping or replacing
patch. Found and fixed twice this session already:

- `window.renderSWExport` had 7 different assignments across the file.
  The one that actually ran on click was the *last* `window.X = ...`
  in file order — not the one that looked most complete when reading top
  to bottom.
- A subtler variant: a bare top-level `function foo(){...}` declaration
  and `window.foo` are **the same binding** in a classic (non-module)
  script. So `window.foo = foo` is a no-op if something *later in the
  file* already reassigned `window.foo` — the bare identifier `foo` on
  the right-hand side has itself already been overwritten by the time
  that line runs. This cost real time on both `renderSWOverview` (fixed
  by renaming the real implementation to a unique name,
  `renderSWExportAudiencePackages`) and in tracing `exportSystemJSON`
  (whose real live chain turned out to be
  `EACEExportService.exportSystem → run → exportOne → fullJson`, several
  layers away from the obvious same-named function).

**Rule: before editing any function that has a `window.X = ` sibling
anywhere else in the file, grep for every assignment to that name and
confirm which one is textually last.** Before claiming a fix works,
**verify it in a live headless browser** (see Testing, below) — reading
the source is not sufficient evidence on this file. If you find and fix
another shadowing case, add it to the list above.

## Editing discipline

- **Small, tested, documented commits.** One logical change per commit;
  explain *why*, not just what, especially when the "why" is "this was
  shadowed and unreachable" or similar non-obvious discoveries.
- **Don't touch P1–P4 prompt/routing/legal logic without being explicitly
  asked to.** Metadata, UI, and export-surface changes are lower-risk and
  don't require touching `buildSystemPrompt`, `CANONICAL_MASTER_TEMPLATES`,
  or the classification engine. If a task's non-regression rule lists
  specific areas as off-limits, treat that literally — additive metadata
  injection is not the same as "editing DOCX/PDF rendering logic."
- **Don't rename or delete historical `vNN` labels, object names, or
  schema identifiers** (`EACE_CASE_EXPORT_V42`, `__eaceV42`,
  `eace-v42-*`, etc.) just because they look old. They're a development
  history, not a competing version scheme — see `BUILD_INFO` below.
- **Never fabricate facts, dates, or legal citations.** If something
  can't be verified from the source or from an authoritative reference,
  say so explicitly rather than inferring or estimating it — this
  project's own documentation set holds itself to that standard; match
  it in code comments and generated content alike.

## BUILD_INFO — the version identity, and only that

`const BUILD_INFO = {...}` (~line 3351) is the single source of truth for
`productVersion` / `engineVersion` / `workspaceSchemaVersion` /
`exportPackageVersion` / `buildId` / `buildDate`. It is deliberately a
*different* taxonomy from the historical `vNN` labels above — BUILD_INFO
is current product identity, `vNN` labels are development provenance.
Never invent a new ad hoc version string anywhere in the file; read from
`BUILD_INFO` (it's a plain global const, safe to reference from any later
script block).

## Regulatory content rules (P1–P4 outputs)

- **Closed badge-token vocabulary**: `[PROHIBITED]`, `[HIGH-RISK]`,
  `[LIMITED-RISK]`, `[MINIMAL-RISK]`, `[OUT-OF-SCOPE]`, `[CONFIRMED]`,
  `[ACTION-REQUIRED]`, `[WARNING]`, `[DOCUMENTATION-REQUIRED]`,
  `[NOT-APPLICABLE]`, `[LEGAL-COUNSEL]`. These are the only tokens with
  real colour rendering wired into both DOCX and PDF export
  (`CAT_COLOR_DOCX` and its PDF equivalent). A new/invented status token
  renders as plain black text — always reuse this vocabulary.
- **P1 has no deployment-approval authority.** Its mandatory status
  vocabulary forbids "GO" / "CONDITIONAL GO" / "APPROVED" in generated
  text. Where a presentation layer needs a GO/NO-GO-style badge (e.g. the
  Overview traffic-light card), map it from the badge token at the
  presentation layer only — never let the underlying P1 text say it.
- **`isP1BriefOutput`**: most P1 outputs outside
  `CORE_P1_CLASSIFICATION_CODES` (OTL, OCL, O01–O06, O13, O14) use a
  compact "brief obligation format" specifically to prevent P1 packages
  from ballooning past ~300 pages. Don't apply the full 7-part structure
  (Executive Dashboard/Summary/Operational Artifact/Legal
  Analysis/Implementation Guidance/Evidence Mapping/Cross References) to
  brief-format outputs — they get a single-line dashboard instead, by
  design.
- **`documentation language` (`authLang`/`outputLanguages`) and `notice
  language` (`noticeLanguages`, Art. 50) are strictly independent
  fields.** A prior bug let one fall back to the other; there's a code
  comment at the point they're read guarding against regression. Never
  make one a fallback for the other.
- **`isSyntheticCase`** marks demonstration/validation systems with
  fabricated data. When true, a literal two-line "SYNTHETIC REGULATORY
  TEST CASE / NO REAL ORGANISATION OR NATURAL PERSON REPRESENTED" marker
  must appear in the Overview banner and in every export surface (DOCX
  banner, PDF cover box, JSON/manifest `syntheticCase` field). It must
  never appear for a real case, and legacy data without the field
  (`undefined`) must never be treated as `=== true`.

## Evidence, audit and export architecture

- Every generated output is linked into an Evidence Layer
  (`sys.evidence[]`, SHA-256 hashes) and an append-only Audit Trail
  (`sys.auditRecords[]`, via `addAuditRecord(...)`) — this is native to
  the app, not something to bolt on. If a new feature changes state,
  log it here; don't treat chat/session history as the audit trail.
- **`window.__eaceV32.buildDocx` / `buildPdf`** (inside the big
  `eace-v30-word-org-targeted-fix` IIFE) are the canonical rendering
  pipeline — reused by `window.__eaceV42.buildCached`, the v47
  `makeDocx`/`makePdf` wrappers, and by extension the Export Centre and
  ZIP export. `buildSingleOutputDocxBlob` (used only by the ZIP's
  `/docs` folder) is a separate, simpler single-output builder. If you
  need to inject something into every generated document (a banner, a
  metadata stamp), these are the two places — not the several other
  `buildDocx`/`makeDocx` copies elsewhere in the file, most of which are
  shadowed and unreachable (see the gotcha above).
- Nine audience-specific export packages (board, executive, legal,
  compliance, technical, auditor, notified_body, vendor_dd, complete) are
  defined in `EXPORT_AUDIENCES` and filtered via `audienceOutputFilter()`
  — all served by the same canonical renderer, not independent code
  paths. `EXPORT_PACKAGES` (5-item, older) is a legacy array still
  referenced by some pre-v42 code paths; don't confuse the two.

## Testing

The app has a **built-in self-test**, `runP1ClassificationIntegrityTests()`
(~line 4748) — 10 checks against the classification engine's actual
business rules (e.g. "a sector alone never yields a final Annex III
classification"), run against an isolated synthetic system so it doesn't
touch real data. This is the fastest real regression signal available and
should pass before any commit that touches P1 logic, routing, or shared
state handling.

`tests/` in this repo wraps that self-test (and a few export/BUILD_INFO
checks assembled this session) in headless-browser scripts, since the app
has no other test harness:

```bash
python3 -m http.server 8899 &          # serve the repo root
python3 tests/regression.py             # runs runP1ClassificationIntegrityTests(), expects 10/10
python3 tests/verify_build_info.py      # BUILD_INFO + isSyntheticCase propagation checks
```

Both require Playwright with a Chromium binary
(`PLAYWRIGHT_BROWSERS_PATH`/`executable_path` — see the scripts). Treat a
script failure or a non-empty `page errors` list as a real regression, not
noise — several bugs this session were only caught this way, not by
reading the diff.

There is no CI wired up for these yet; run them manually before pushing
anything that touches classification, routing, export rendering, or
BUILD_INFO/synthetic-case propagation.

## Git workflow

Small, focused commits with commit messages that explain *why* — this
file's own history is the best model to follow (`git log --oneline`).
Push to the feature branch in use; do not push to `main` directly unless
explicitly asked.
