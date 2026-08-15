"""
Live check for the Step 2 P0 OPERATIONAL ENRICHMENT blocks in
buildSystemPrompt(): Human Oversight (P2A O08, P2B O09 — NOT P2B O08,
which is "Art. 50 transparency notice package", a mislabelling corrected
during this step) and the Fundamental Rights Matrix (P2B O06, the
dedicated FRIA catalogue slot). Confirms each marker appears only on its
intended output and nowhere else nearby (P2A O07/O09, P2B O05/O08/O10),
so the correction doesn't leak onto an adjacent code.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step2_p0_enrichment.py
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

HO_MARK = "P0 OPERATIONAL ENRICHMENT — HUMAN OVERSIGHT"
FRIA_MARK = "P0 OPERATIONAL ENRICHMENT — FUNDAMENTAL RIGHTS MATRIX"

# (pillar, code, expect_ho, expect_fria)
CHECKS = [
    ("P2A", "O08", True, False),   # Human oversight specification
    ("P2A", "O07", False, False),  # Instructions for use — must NOT carry it
    ("P2A", "O09", False, False),  # QA and cybersecurity framework — must NOT carry it
    ("P2B", "O09", True, False),   # Human oversight deployment protocol (corrected code)
    ("P2B", "O08", False, False),  # Art.50 transparency notice package — must NOT carry it (the mislabelled code)
    ("P2B", "O10", False, False),  # Logging and monitoring implementation record — must NOT carry it
    ("P2B", "O06", False, True),   # FRIA — dedicated slot
    ("P2B", "O05", False, False),  # DPIA — shares canonical source with O06 but must NOT get the FRIA matrix block
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "Step2Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []
    for pillar, code, expect_ho, expect_fria in CHECKS:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        if out is None:
            fails.append(f"{pillar}/{code}: not found in OUTPUTS")
            continue
        result = page.evaluate(
            "([pillar, out]) => buildSystemPrompt(pillar, out).perCall",
            [pillar, out],
        )
        has_ho = HO_MARK in result
        has_fria = FRIA_MARK in result
        ok = (has_ho == expect_ho) and (has_fria == expect_fria)
        print(f"{'OK' if ok else 'FAIL'}  {pillar}/{code} ({out['title']}): HO={has_ho}(expect {expect_ho}) FRIA={has_fria}(expect {expect_fria})")
        if not ok:
            fails.append(f"{pillar}/{code}: HO={has_ho} expected {expect_ho}, FRIA={has_fria} expected {expect_fria}")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
