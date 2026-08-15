"""
Live check for the Step 1 OPERATIONAL ARTEFACT COMPLETENESS CONTRACT:
present in buildSystemPrompt() for P2A/P2B/P3/P4 non-CSV outputs, absent
for P1 (analytical pillar) and for CSV-A/CSV-B exports on every pillar
(raw-CSV outputs must not carry table/matrix-oriented instructions).
Also spot-checks the artefact-type detection heuristic on a few real
outputs to confirm sane type assignment.
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

MARK = "OPERATIONAL ARTEFACT COMPLETENESS CONTRACT"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "Step1Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    checks = [
        ("P1", "O03", False, "Annex III point-by-point evaluation"),
        ("P2A", "O01", True, "Responsibility matrix and actor register"),
        ("P2A", "CSV-A", False, "Machine-readable export — provider obligations"),
        ("P2B", "O25", None, "Executive summary — deployer package"),  # O25 doesn't exist in P2B(22) -> skip via None marker below
        ("P2B", "O05", True, "DPIA — Data Protection Impact Assessment"),
        ("P3", "G01", True, "Art. 50(1) AI interaction disclosure notice"),
        ("P4", "UM0", True, "Art. 95 minimal-risk affirmation"),
    ]

    fails = []
    for pillar, code, expect_present, _label in checks:
        if expect_present is None:
            continue
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        if out is None:
            fails.append(f"{pillar}/{code}: not found in OUTPUTS")
            continue
        result = page.evaluate(
            "([pillar, out]) => buildSystemPrompt(pillar, out).perCall",
            [pillar, out],
        )
        present = MARK in result
        status = "OK" if present == expect_present else "FAIL"
        print(f"{status}  {pillar}/{code} ({out['title']}): contract present={present}, expected={expect_present}")
        if present != expect_present:
            fails.append(f"{pillar}/{code}: expected contract present={expect_present}, got {present}")

    # artefact-type spot checks
    type_checks = [
        ("P2A", "O01", ["MATRIX", "REGISTER"]),      # Responsibility matrix and actor register
        ("P2B", "O05", ["DPIA"]),                     # DPIA output
        ("P2A", "O25", ["CONTRACT"]),                 # Contractual instrument package
        ("P3", "G01", ["NOTICE"]),                     # Art.50(1) disclosure notice
    ]
    for pillar, code, expect_substrings in type_checks:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        result = page.evaluate(
            "([pillar, out]) => buildSystemPrompt(pillar, out).perCall",
            [pillar, out],
        )
        idx = result.find(MARK)
        window = result[idx:idx+1600] if idx >= 0 else ""
        for sub in expect_substrings:
            ok = sub in window
            print(f"{'OK' if ok else 'FAIL'}  {pillar}/{code} type-detect contains {sub!r}")
            if not ok:
                fails.append(f"{pillar}/{code}: expected artefact type marker {sub!r} in contract block")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
