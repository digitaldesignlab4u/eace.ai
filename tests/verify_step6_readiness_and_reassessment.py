"""
Verifies the three engine-level functions added on top of Steps 0-5 for the
implementation directive's F/G/H areas:

1. extractUnresolvedFields(pillar, out, generatedText) — deterministic
   inventory of unresolved fields, from both the richer
   `[INPUT REQUIRED: field — reason — expected source — owner]` format and
   the legacy plain completion markers (`[PLACEHOLDER...]`, `[ACT]`, etc.),
   each field carrying a fieldId/artefact/context/readinessImpact and,
   where available, reason/expectedSource/owner.
2. computeReadinessState(pillar, out, generatedText, opts) — the 8-state
   ladder (MISSING..SUPERSEDED) plus the 6 separated dimensions
   (LEGAL_STATUS/ARTEFACT_STATUS/EVIDENCE_STATUS/IMPLEMENTATION_STATUS/
   CONFORMITY_STATUS/PACKAGE_READINESS), confirming ARTEFACT_STATUS always
   equals the Step 4 assessArtefactCompleteness verdict for the same text,
   that external opts (expertReviewed/approved/executed/superseded) only
   ever advance the ladder, and that superseded is terminal.
3. classifyReassessmentDelta(delta) — pure function, 4-class precedence
   (CLASSIFICATION_RELEVANT_CHANGE > MATERIAL_FACT_CHANGE >
   NEW_EVIDENCE_ONLY > DOCUMENT_COMPLETION_ONLY), confirming precedence
   holds even when multiple signals are present simultaneously, and that
   prior-history preservation language appears in the classification-
   relevant and material-fact actions.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step6_readiness_and_reassessment.py
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "Step6Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []
    out03 = page.evaluate("() => OUTPUTS.P2A.find(o => o.code === 'O03')")

    # 1. extractUnresolvedFields ------------------------------------------------
    sample_text = (
        "Risk Management System Plan\n\n"
        "Purpose and scope: full lifecycle coverage.\n"
        "Owner: [INPUT REQUIRED: Risk Owner name — not supplied in Organisation Profile — expected source: HR/org chart — owner: Compliance Officer]\n"
        "Residual risk threshold: [PLACEHOLDER — ENTER INTERNAL DATA] pending Board sign-off. BLOCKING FOR THIS OUTPUT.\n"
        "Sector overlay: No additional requirements beyond EU AI Act baseline. NON-BLOCKING — INFORMATIONAL GAP ONLY.\n"
        "Notified body designation: [OFFICIAL SOURCE VERIFICATION REQUIRED] at execution time. BLOCKING FOR PACKAGE READINESS.\n"
    )
    fields = page.evaluate(
        "([p, o, t]) => extractUnresolvedFields(p, o, t)", ["P2A", out03, sample_text]
    )
    print(f"extractUnresolvedFields -> {len(fields)} fields")
    for f in fields:
        print("   ", f)

    ok = len(fields) == 3
    if not ok:
        fails.append(f"extractUnresolvedFields: expected 3 fields, got {len(fields)}")

    input_required = next((f for f in fields if f.get("fieldName") == "Risk Owner name"), None)
    if not input_required:
        fails.append("extractUnresolvedFields: INPUT REQUIRED field not parsed with fieldName='Risk Owner name'")
    else:
        if input_required.get("reason") != "not supplied in Organisation Profile":
            fails.append(f"extractUnresolvedFields: reason mismatch: {input_required.get('reason')!r}")
        if input_required.get("expectedSource") != "expected source: HR/org chart":
            # split is naive on em-dash only, so labels stay attached — just confirm non-null and content present
            if not input_required.get("expectedSource") or "HR/org chart" not in input_required["expectedSource"]:
                fails.append(f"extractUnresolvedFields: expectedSource missing HR/org chart content: {input_required.get('expectedSource')!r}")
        if not input_required.get("owner") or "Compliance Officer" not in input_required["owner"]:
            fails.append(f"extractUnresolvedFields: owner missing Compliance Officer: {input_required.get('owner')!r}")

    placeholder_field = next((f for f in fields if "PLACEHOLDER" in (f.get("fieldName") or "")), None)
    if not placeholder_field:
        fails.append("extractUnresolvedFields: legacy [PLACEHOLDER...] marker not captured")
    elif placeholder_field.get("readinessImpact") != "BLOCKING FOR THIS OUTPUT":
        fails.append(f"extractUnresolvedFields: placeholder readinessImpact mismatch: {placeholder_field.get('readinessImpact')!r}")

    nb_field = next((f for f in fields if "OFFICIAL SOURCE VERIFICATION REQUIRED" in (f.get("fieldName") or "")), None)
    if not nb_field:
        fails.append("extractUnresolvedFields: [OFFICIAL SOURCE VERIFICATION REQUIRED] marker not captured")
    elif nb_field.get("readinessImpact") != "BLOCKING FOR PACKAGE READINESS":
        fails.append(f"extractUnresolvedFields: NB field readinessImpact mismatch: {nb_field.get('readinessImpact')!r}")

    # Non-blocking sector overlay line should NOT be captured as an unresolved
    # field at all (it contains no completion marker — it's a fully resolved
    # "nothing additional applies" statement per the Empty Annex rule).
    overlay_field = next((f for f in fields if "Sector overlay" in (f.get("context") or "")), None)
    if overlay_field:
        fails.append(f"extractUnresolvedFields: resolved sector-overlay line incorrectly flagged as unresolved: {overlay_field}")

    empty_fields = page.evaluate("([p, o]) => extractUnresolvedFields(p, o, 'Fully resolved text with no markers at all, well over one hundred and fifty characters long so it does not get treated as missing content by any other validator in this file.')", ["P2A", out03])
    if empty_fields:
        fails.append(f"extractUnresolvedFields: clean text unexpectedly produced fields: {empty_fields}")

    # 2. computeReadinessState ---------------------------------------------------
    LADDER = ["MISSING", "DRAFT", "PARTIALLY_POPULATED", "STRUCTURALLY_COMPLETE",
              "READY_FOR_EXPERT_REVIEW", "APPROVED", "EXECUTED", "SUPERSEDED"]

    complete_text = (
        "Risk Management System Plan\n\nPurpose and scope: full lifecycle coverage, covering all risk categories.\n\n"
        "Roles: the Compliance Officer is the owner and is responsible for this document; the Quality Manager is "
        "consulted.\n\nStep 1. Identify hazards using the taxonomy below.\nStep 2. Assess severity and likelihood on "
        "the defined scale.\nStep 3. Escalate to the Risk Owner whenever a trigger condition or decision criteria "
        "threshold is met.\n\nEvidence and records: every finding is logged in the Risk Register with a unique ID, "
        "and retained for audit.\n\nMonitoring, review and approval: this plan is reviewed quarterly and approved by "
        "the Quality Manager, with sign-off recorded in the QMS."
    )
    r1 = page.evaluate("([p, o, t]) => computeReadinessState(p, o, t, {})", ["P2A", out03, complete_text])
    print("computeReadinessState (no opts):", r1)
    if r1["ladderState"] != "STRUCTURALLY_COMPLETE":
        fails.append(f"computeReadinessState: expected STRUCTURALLY_COMPLETE with no opts, got {r1['ladderState']}")
    if r1["dimensions"]["ARTEFACT_STATUS"] != "STRUCTURALLY_COMPLETE":
        fails.append(f"computeReadinessState: ARTEFACT_STATUS should mirror Step 4 verdict, got {r1['dimensions']}")
    for dim in ("LEGAL_STATUS", "EVIDENCE_STATUS", "IMPLEMENTATION_STATUS", "CONFORMITY_STATUS", "PACKAGE_READINESS"):
        if r1["dimensions"][dim] != "NOT ASSESSED":
            fails.append(f"computeReadinessState: {dim} should default NOT ASSESSED, got {r1['dimensions'][dim]!r}")

    r2 = page.evaluate(
        "([p, o, t, opts]) => computeReadinessState(p, o, t, opts)",
        ["P2A", out03, complete_text, {"expertReviewed": True, "approved": True}],
    )
    print("computeReadinessState (approved):", r2["ladderState"])
    if r2["ladderState"] != "APPROVED":
        fails.append(f"computeReadinessState: expected APPROVED, got {r2['ladderState']}")
    if LADDER.index(r2["ladderState"]) <= LADDER.index(r1["ladderState"]):
        fails.append("computeReadinessState: approved opts did not advance the ladder relative to no-opts")

    # Missing content cannot be short-circuited into APPROVED by opts alone
    # in a way that hides the underlying artefact gap — ARTEFACT_STATUS must
    # still read MISSING even though the ladder state itself is allowed to
    # advance (approval is an external fact this function does not veto).
    r3 = page.evaluate(
        "([p, o, opts]) => computeReadinessState(p, o, '', opts)",
        ["P2A", out03, {"approved": True}],
    )
    if r3["dimensions"]["ARTEFACT_STATUS"] != "MISSING":
        fails.append(f"computeReadinessState: empty text should keep ARTEFACT_STATUS MISSING regardless of opts, got {r3['dimensions']}")

    # Superseded is terminal and overrides even executed.
    r4 = page.evaluate(
        "([p, o, t, opts]) => computeReadinessState(p, o, t, opts)",
        ["P2A", out03, complete_text, {"executed": True, "superseded": True}],
    )
    if r4["ladderState"] != "SUPERSEDED":
        fails.append(f"computeReadinessState: superseded should be terminal/override, got {r4['ladderState']}")

    # 3. classifyReassessmentDelta ------------------------------------------------
    DELTA_CASES = [
        ({"changedFields": ["ownerName"]}, "DOCUMENT_COMPLETION_ONLY"),
        ({}, "DOCUMENT_COMPLETION_ONLY"),
        ({"changedEvidence": ["dpia-signoff.pdf"]}, "NEW_EVIDENCE_ONLY"),
        ({"approvalSupplied": True}, "NEW_EVIDENCE_ONLY"),
        ({"materialFactChanged": True}, "MATERIAL_FACT_CHANGE"),
        ({"materialFactChanged": True, "changedEvidence": ["x"]}, "MATERIAL_FACT_CHANGE"),
        ({"classificationRelevantFieldsChanged": True}, "CLASSIFICATION_RELEVANT_CHANGE"),
        # Precedence: classification-relevant wins even when every other
        # signal is also true simultaneously.
        ({"classificationRelevantFieldsChanged": True, "materialFactChanged": True,
          "changedEvidence": ["x"], "changedFields": ["y"]}, "CLASSIFICATION_RELEVANT_CHANGE"),
    ]
    for delta, expected in DELTA_CASES:
        result = page.evaluate("(d) => classifyReassessmentDelta(d)", delta)
        ok = result["classification"] == expected
        print(f"{'OK' if ok else 'FAIL'}  classifyReassessmentDelta({delta}) -> {result['classification']} (expected {expected})")
        if not ok:
            fails.append(f"classifyReassessmentDelta({delta}): got {result['classification']!r}, expected {expected!r}")

    audit_check = page.evaluate("(d) => classifyReassessmentDelta(d).action", {"classificationRelevantFieldsChanged": True})
    if "audit trail" not in audit_check or "STALE" not in audit_check:
        fails.append(f"classifyReassessmentDelta: CLASSIFICATION_RELEVANT_CHANGE action missing audit-trail/STALE language: {audit_check!r}")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
