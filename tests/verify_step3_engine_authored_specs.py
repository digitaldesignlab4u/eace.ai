"""
Verifies the 8 Step 0 NO_DEDICATED_SECTION gaps now have real,
engine-authored canonical specifications (Step 3, ENGINE_AUTHORED_SPECS in
index.html) and resolve RESOLVED, not NO_DEDICATED_SECTION.

Checks for each of the 8 codes:
- getCanonicalSpecStatus flips to RESOLVED once extracted.
- The returned text is substantive (not the short status-record fallback —
  asserted by length and by absence of the "Do NOT draft the substantive
  artefact" marker, which only appears in the genuine NO_DEDICATED_SECTION
  fallback).
- house-style markers ("Legal basis:", "Generate:") are present, matching
  every other real canonical section.
- For P2A O25 / P2B O18 specifically (contractual instruments — flagged as
  the highest-priority gap), confirm all 7 named instruments appear.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step3_engine_authored_specs.py
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

GAPS = [
    ("P2A", "O24"), ("P2A", "O25"), ("P2A", "O29"), ("P2A", "O30"), ("P2A", "O31"),
    ("P2B", "O02"), ("P2B", "O14"), ("P2B", "O18"),
]

INSTRUMENT_NAMES = [
    "IFU Acknowledgement", "Data Processing Agreement", "PMM Data-Sharing Agreement",
    "Incident Reporting Protocol Agreement", "Substantial Modification Clause",
    "Suspension Rights Agreement", "Governing Law", "Jurisdiction",
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "Step3SpecCheck", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []
    for pillar, code in GAPS:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        if out is None:
            fails.append(f"{pillar}/{code}: not found in OUTPUTS")
            continue
        result = page.evaluate(
            "([pillar, out]) => extractCanonicalOutputBlock(pillar, out)",
            [pillar, out],
        )
        status = page.evaluate(f"() => getCanonicalSpecStatus('{pillar}','{code}')")
        is_substantive = len(result) > 800 and "Legal basis:" in result and "Generate" in result
        is_status_only = "Do NOT draft the substantive artefact" in result
        ok = status == "RESOLVED" and is_substantive and not is_status_only
        print(f"{'OK' if ok else 'FAIL'}  {pillar}/{code}: status={status} len={len(result)} substantive={is_substantive}")
        if not ok:
            fails.append(f"{pillar}/{code}: status={status}, substantive={is_substantive}, status-only-fallback={is_status_only}")

        if code in ("O25", "O18"):
            missing = [n for n in INSTRUMENT_NAMES if n not in result]
            if missing:
                fails.append(f"{pillar}/{code}: missing named instrument(s): {missing}")
            else:
                print(f"    all 7 named instruments present in {pillar}/{code}")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
