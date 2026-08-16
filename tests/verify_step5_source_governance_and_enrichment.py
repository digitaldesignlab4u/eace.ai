"""
Verifies the implementation-directive changes layered on top of Steps 0-4:

1. buildGlobalRegulatoryGovernance() additions (apply to every pillar via
   the shared `cacheable` prompt segment): the SOURCE-STATUS LABELLING
   four-way vocabulary, the NOTIFIED BODY / CONFORMITY MATERIAL hierarchy,
   and the EMPTY ANNEX / EMPTY ARTEFACT RULE.
2. The Vulnerability column added to P2B O06's Fundamental Rights Matrix.
3. Step 3B priority-enrichment blocks (buildSystemPrompt) land on exactly
   their intended P2A/P2B output and nowhere else nearby.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step5_source_governance_and_enrichment.py
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
        page.fill('input[placeholder="Name or identifier"]', "Step5Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []

    # 1. Global governance additions present for every pillar.
    GLOBAL_MARKERS = [
        "SOURCE-STATUS LABELLING",
        "DRAFT OFFICIAL GUIDANCE",
        "NOTIFIED BODY / CONFORMITY MATERIAL",
        "CLIENT-SPECIFIC NB FINDING",
        "EMPTY ANNEX / EMPTY ARTEFACT RULE",
    ]
    for pillar, code in [("P1", "O03"), ("P2A", "O01"), ("P2B", "O01"), ("P3", "G01"), ("P4", "UM0")]:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        result = page.evaluate("([p, o]) => buildSystemPrompt(p, o).cacheable", [pillar, out])
        for marker in GLOBAL_MARKERS:
            ok = marker in result
            if not ok:
                fails.append(f"{pillar}/{code}: missing global governance marker {marker!r}")
        print(f"{'OK' if all(m in result for m in GLOBAL_MARKERS) else 'FAIL'}  {pillar}/{code}: all {len(GLOBAL_MARKERS)} global markers present")

    # 2. Vulnerability column on P2B O06 FRIA matrix, absent elsewhere.
    out06 = page.evaluate("() => OUTPUTS.P2B.find(o => o.code === 'O06')")
    perCall06 = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", ["P2B", out06])
    has_vuln_column = "Affected Person/Group | Vulnerability | Impact Mechanism" in perCall06
    print(f"{'OK' if has_vuln_column else 'FAIL'}  P2B/O06: Vulnerability column present in exact column order")
    if not has_vuln_column:
        fails.append("P2B/O06: Vulnerability column missing or out of order")

    out05 = page.evaluate("() => OUTPUTS.P2B.find(o => o.code === 'O05')")
    perCall05 = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", ["P2B", out05])
    if "Vulnerability | Impact Mechanism" in perCall05:
        fails.append("P2B/O05 (DPIA): unexpectedly contains the FRIA Vulnerability column instruction")

    # 3. Step 3B priority-enrichment targeting.
    CHECKS = [
        ("P2A", "O03", "PRIORITY ENRICHMENT — RISK MANAGEMENT SYSTEM", True),
        ("P2A", "O04", "PRIORITY ENRICHMENT — DATA GOVERNANCE", True),
        ("P2A", "O07", "PRIORITY ENRICHMENT — INSTRUCTIONS FOR USE", True),
        ("P2A", "O11", "PRIORITY ENRICHMENT — QMS MANUAL", True),
        ("P2A", "O12", "LAST VERIFIED BASELINE", True),
        ("P2A", "O12", "NB DESIGNATION STATUS UNVERIFIED", True),
        ("P2A", "O13", "PRIORITY ENRICHMENT — CONFORMITY VERIFICATION", True),
        ("P2A", "O17", "PRIORITY ENRICHMENT — POST-MARKET MONITORING", True),
        ("P2A", "O18", "PRIORITY ENRICHMENT — INCIDENT REPORTING PROTOCOL", True),
        ("P2A", "O23", "PRIORITY ENRICHMENT — VERIFICATION AND VALIDATION", True),
        ("P2B", "O10", "PRIORITY ENRICHMENT — LOGGING AND MONITORING", True),
        ("P2B", "O11", "PRIORITY ENRICHMENT — INCIDENT DETECTION", True),
        ("P2B", "O13", "PRIORITY ENRICHMENT — NIS2", True),
        ("P2B", "O19", "PRIORITY ENRICHMENT — SUBSTANTIAL MODIFICATION", True),
        ("P2B", "O21", "PRIORITY ENRICHMENT — SECTOR OVERLAY", True),
        # Added following the Golden Artefact Acceptance dry-run (static pre-flight
        # audit): O02 was flagged as "unaudited" — its own spec is an index/skeleton
        # correctly cross-referencing O03/O04/O07/O08/O09 for 5 of 9 Annex IV
        # blocks, but Blocks 1/2/3/9 have no other home and needed real depth.
        ("P2A", "O02", "PRIORITY ENRICHMENT — ANNEX IV DOCUMENTATION SKELETON", True),
        # O09's canonical spec cites the combined shorthand "Art. 14+26"; this
        # enrichment requires the model to cite Art. 14 (provider design, inherited)
        # and Art. 26(5) (the deployer's own oversight-assignment duty) separately.
        ("P2B", "O09", "Article 26(5)", True),
        # Negative checks: outputs the audit found already strong should get NO priority-enrichment block.
        ("P2A", "O22", "PRIORITY ENRICHMENT", False),
        ("P2A", "O27", "PRIORITY ENRICHMENT", False),
        ("P2A", "O28", "PRIORITY ENRICHMENT", False),
        ("P2B", "O12", "PRIORITY ENRICHMENT", False),
        ("P2B", "O15", "PRIORITY ENRICHMENT", False),
        ("P2B", "O16", "PRIORITY ENRICHMENT", False),
        ("P2B", "O17", "PRIORITY ENRICHMENT", False),
    ]
    for pillar, code, marker, expect_present in CHECKS:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        result = page.evaluate("([p, o]) => buildSystemPrompt(p, o).perCall", [pillar, out])
        present = marker in result
        ok = present == expect_present
        print(f"{'OK' if ok else 'FAIL'}  {pillar}/{code}: {marker!r} present={present} (expected {expect_present})")
        if not ok:
            fails.append(f"{pillar}/{code}: {marker!r} present={present}, expected {expect_present}")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
