"""
Verifies Step 4's deterministic artefact-completeness validator
(assessArtefactCompleteness, index.html): given generated output text, it
must classify into exactly one of the five specified states — MISSING /
PRESENT / PARTIALLY_POPULATED / REQUIRES_INTERNAL_COMPLETION /
STRUCTURALLY_COMPLETE — by rule (keyword/structure presence), not by
trusting the model's own claim of completeness.

This test calls the pure function directly with synthetic text (no API
key, no live generation, no cost) to exercise all five states
deterministically. It does NOT verify the execRun() wiring that stores
the result on a real generated output (out.completeness) — that requires
an actual paid generation and belongs to Step 6's live acceptance run, not
this static/structural check. The wiring code itself was added at the
same point validateGeneratedOutput() already runs (see git log).

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step4_completeness_validator.py
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

# A synthetic P2A O03 (RMS — SOP_PROCEDURE-detected) output at 5 stages of
# completeness, engineered to hit each of the 5 states in turn.
CASES = [
    ("empty", "", "MISSING"),
    ("too short", "This is the RMS.", "MISSING"),
    ("no-dedicated-section echo",
     "CANONICAL SPECIFICATION STATUS: No dedicated canonical specification is currently defined for this output.\n\n"
     + ("padding " * 40),
     "MISSING"),
    ("thin content, low coverage",
     "Risk Management System Plan\n\nThis document is a general overview of risk practices at the organisation. "
     + ("General narrative text without structure. " * 20),
     "PRESENT"),
    ("partial anatomy",
     "Risk Management System Plan\n\nPurpose and scope: this RMS covers the AI system's full lifecycle.\n\n"
     "Roles: the Compliance Officer owns this document.\n\n"
     + ("Further narrative discussion of risk without steps, triggers, escalation, evidence or review. " * 15),
     "PARTIALLY_POPULATED"),
    ("full anatomy but with a placeholder marker",
     "Risk Management System Plan\n\nPurpose and scope: full lifecycle coverage. Roles: Compliance Officer is owner "
     "and responsible party.\n\nStep 1. Identify hazards.\nStep 2. Assess severity and likelihood scale.\n"
     "Step 3. Escalate to the Risk Owner when a trigger condition is met, per the defined decision criteria.\n\n"
     "Evidence: all findings are recorded in the Risk Register.\n\nReview and approval: reviewed quarterly and "
     "approved by the Quality Manager.\n\nOutstanding item: [PLACEHOLDER — ENTER INTERNAL DATA] for the residual "
     "risk acceptance threshold.",
     "REQUIRES_INTERNAL_COMPLETION"),
    ("full anatomy, no markers",
     "Risk Management System Plan\n\nPurpose and scope: full lifecycle coverage, covering all risk categories.\n\n"
     "Roles: the Compliance Officer is the owner and is responsible for this document; the Quality Manager is "
     "consulted.\n\nStep 1. Identify hazards using the taxonomy below.\nStep 2. Assess severity and likelihood on "
     "the defined scale.\nStep 3. Escalate to the Risk Owner whenever a trigger condition or decision criteria "
     "threshold is met.\n\nEvidence and records: every finding is logged in the Risk Register with a unique ID, "
     "and retained for audit.\n\nMonitoring, review and approval: this plan is reviewed quarterly and approved by "
     "the Quality Manager, with sign-off recorded in the QMS.",
     "STRUCTURALLY_COMPLETE"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "Step4Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    out = page.evaluate("() => OUTPUTS.P2A.find(o => o.code === 'O03')")
    fails = []
    for label, text, expected in CASES:
        result = page.evaluate(
            "([pillar, out, text]) => assessArtefactCompleteness(pillar, out, text)",
            ["P2A", out, text],
        )
        ok = result["status"] == expected
        print(f"{'OK' if ok else 'FAIL'}  {label}: status={result['status']} (expected {expected}) coverage={result.get('coverage')} markers={result.get('completionMarkersFound')}")
        if not ok:
            fails.append(f"{label}: got {result['status']!r}, expected {expected!r} — full: {result}")

    # Sanity: function is reused-taxonomy-consistent with detectArtefactTypes / ARTEFACT_MIN_ANATOMY
    consistency = page.evaluate("""() => {
        const out = OUTPUTS.P2A.find(o => o.code === 'O25'); // Contractual instrument package
        const types = detectArtefactTypes(out);
        const result = assessArtefactCompleteness('P2A', out, extractCanonicalOutputBlock('P2A', out));
        return { types, resultTypes: result.types, status: result.status, coverage: result.coverage };
    }""")
    print("Type-taxonomy consistency check (P2A O25):", consistency)
    if consistency["types"] != consistency["resultTypes"]:
        fails.append(f"detectArtefactTypes and assessArtefactCompleteness disagree on types for P2A/O25: {consistency}")
    # The engine-authored O25 spec itself is a well-formed CONTRACT-shaped
    # document (clauses, parties, obligations language) — sanity-check it
    # scores at least PARTIALLY_POPULATED, not PRESENT/MISSING.
    if consistency["status"] not in ("PARTIALLY_POPULATED", "STRUCTURALLY_COMPLETE", "REQUIRES_INTERNAL_COMPLETION"):
        fails.append(f"P2A/O25's own authored spec text scored unexpectedly low: {consistency}")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
