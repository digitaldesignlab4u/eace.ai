"""
Task K — Executive Decision/Status layer. Rather than adding a second,
competing decision table (which would duplicate What/Legal Basis/Owner
already in the pre-existing Executive Dashboard section from an earlier
session phase and inflate length against this app's own anti-bloat
Drafting Rule 4), this session extended that same Executive Dashboard
table with three new columns — Readiness State / Operational Result /
Artefact Completeness — giving every "major artefact" (every non-CSV,
non-P1-brief output) the Current-State/Legal-Position/Operational-Result/
Artefact-Status/Evidence-Status/Remaining-Completion-Items/Next-Action
view the implementation directive asked for, composed from What+Readiness
State+Operational Result+Status+Artefact Completeness+Missing Evidence+
Required Actions across the (now ten-column) table, before the
substantive content sections that follow it (Operational Artifact, Legal
Analysis, etc.).

This test confirms:
1. The three new columns are present in the Executive Dashboard
   instruction for eligible outputs (P2A/P2B/P3/P4 non-CSV, and P1's core
   classification outputs), and absent for CSV exports and P1's brief-
   format outputs (same scoping as the pre-existing Dashboard section,
   verified by tests/verify_step1_contract.py for the parent contract).
2. The Readiness State vocabulary listed in the prompt instruction is
   character-for-character identical to the live READINESS_LADDER
   constant (index.html) that the engine-side computeReadinessState
   function (tests/verify_step6_readiness_and_reassessment.py) actually
   uses — so the prompt-side instruction and the engine-side deterministic
   validator can never silently drift onto different vocabularies, the
   same discipline already established for detectArtefactTypes/
   ARTEFACT_MIN_ANATOMY.
3. The Artefact Completeness vocabulary listed matches the five states
   assessArtefactCompleteness actually returns.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step9_executive_decision_layer.py
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
        page.fill('input[placeholder="Name or identifier"]', "Step9Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []

    NEW_COLUMN_MARKERS = ["Readiness State", "Operational Result", "Artefact Completeness"]

    # 1. Presence for eligible (non-CSV, non-P1-brief) outputs.
    ELIGIBLE = [("P2A", "O03"), ("P2B", "O05"), ("P3", "G01"), ("P4", "UM0")]
    for pillar, code in ELIGIBLE:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        perCall = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", [pillar, out])
        ok = all(m in perCall for m in NEW_COLUMN_MARKERS)
        print(f"{'OK' if ok else 'FAIL'}  {pillar}/{code}: Executive Dashboard extension columns present={ok}")
        if not ok:
            fails.append(f"{pillar}/{code}: missing one or more of {NEW_COLUMN_MARKERS}")

    # 2. Absence for CSV machine-readable exports and P1 brief-format outputs.
    NEGATIVE = [("P1", "CSV-A"), ("P2A", "CSV-A")]
    for pillar, code in NEGATIVE:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        if not out:
            continue
        perCall = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", [pillar, out])
        present = any(m in perCall for m in NEW_COLUMN_MARKERS)
        print(f"{'OK' if not present else 'FAIL'}  {pillar}/{code}: extension columns absent (CSV export)={not present}")
        if present:
            fails.append(f"{pillar}/{code}: Executive Dashboard extension unexpectedly present in a CSV export")

    # O03 is in CORE_P1_CLASSIFICATION_CODES (full format, not brief) — pick
    # an actual brief-format P1 output (outside that core set) instead.
    core_codes = page.evaluate("() => [...CORE_P1_CLASSIFICATION_CODES]")
    p1_brief_candidate = page.evaluate(
        "(core) => OUTPUTS.P1.find(o => !core.includes(o.code) && !/^CSV-/.test(o.code))",
        core_codes,
    )
    if p1_brief_candidate:
        perCall = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", ["P1", p1_brief_candidate])
        present = any(m in perCall for m in NEW_COLUMN_MARKERS)
        label = f"P1/{p1_brief_candidate['code']} (brief format)"
        print(f"{'OK' if not present else 'FAIL'}  {label}: extension columns absent={not present}")
        if present:
            fails.append(f"{label}: Executive Dashboard extension unexpectedly present in a brief-format output")

    # 3. Vocabulary consistency: prompt text vs live engine constants.
    ladder = page.evaluate("() => READINESS_LADDER")
    out03 = page.evaluate("() => OUTPUTS.P2A.find(o => o.code === 'O03')")
    perCall = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", ["P2A", out03])
    ladder_str = ' / '.join(ladder)
    ok = ladder_str in perCall
    print(f"{'OK' if ok else 'FAIL'}  Readiness State vocabulary in prompt matches live READINESS_LADDER exactly: {ok}")
    print("   READINESS_LADDER:", ladder_str)
    if not ok:
        fails.append(f"Prompt's Readiness State vocabulary does not character-match READINESS_LADDER: {ladder_str!r} not found in perCall text")

    completeness_states = ["MISSING", "PRESENT", "PARTIALLY_POPULATED", "REQUIRES_INTERNAL_COMPLETION", "STRUCTURALLY_COMPLETE"]
    completeness_str = ' / '.join(completeness_states)
    ok2 = completeness_str in perCall
    print(f"{'OK' if ok2 else 'FAIL'}  Artefact Completeness vocabulary in prompt matches assessArtefactCompleteness's 5 states: {ok2}")
    if not ok2:
        fails.append(f"Prompt's Artefact Completeness vocabulary does not match: {completeness_str!r} not found in perCall text")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
