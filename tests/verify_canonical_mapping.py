"""
Verifies the Step 0 canonical-mapping fix in extractCanonicalOutputBlock()
(index.html): for every P2A/P2B output with a non-null entry in
OUTPUT_CANONICAL_ANCHORS, the function must now return text that begins
with that output's real "OUTPUT NN  ·" canonical header (not a fragment of
the front-matter status-board table, which is what every output used to
silently resolve to before this fix — see the audit finding in the code
comment above OUTPUT_CANONICAL_ANCHORS). For every output with a `null`
entry in OUTPUT_CANONICAL_ANCHORS, it must resolve via one of two paths:
Step 3's ENGINE_AUTHORED_SPECS (now covers all 8 of the codes that were
null at Step 0 — status RESOLVED, substantive content) or, for any future
`null` code not yet authored, the non-fabricating "CANONICAL SPECIFICATION
STATUS" status record (see verify_mapping_safeguard.py for the full
three-state contract and verify_step3_engine_authored_specs.py for
instrument-level detail on the 8 authored specs) — never a spurious match.

This is a live-engine check, not a static read of the source — per
CLAUDE.md's documented discipline on this file, reading the source is not
sufficient evidence of what the app actually resolves at runtime.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_canonical_mapping.py
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

ANCHORS = {
    "P2A": {
        "O01": 1, "O02": 2, "O03": 3, "O04": 4, "O05": 4, "O06": 6, "O07": 7,
        "O08": 8, "O09": 9, "O10": 9, "O11": 11, "O12": 12, "O13": 13,
        "O14": 14, "O15": 15, "O16": 16, "O17": 17, "O18": 18, "O19": 19,
        "O20": 20, "O21": 21, "O22": 22, "O23": 23, "O24": None, "O25": None,
        "O26": 26, "O27": 27, "O28": 28, "O29": None, "O30": None, "O31": None,
    },
    "P2B": {
        "O01": 1, "O02": None, "O03": 3, "O04": 4, "O05": 25, "O06": 25,
        "O07": 26, "O08": 14, "O09": 8, "O10": 7, "O11": 19, "O12": 18,
        "O13": 9, "O14": None, "O15": 31, "O16": 20, "O17": 30, "O18": None,
        "O19": 29, "O20": 22, "O21": 22, "O22": 24,
    },
}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE_URL, wait_until="networkidle")

        if "ENTER WORKSPACE" in page.inner_text("body"):
            page.fill('input[placeholder="Name or identifier"]', "MappingCheck", timeout=3000)
            page.click("text=ENTER WORKSPACE", timeout=3000)
            page.wait_for_timeout(1000)

        fails = []
        checked = 0
        for pillar, codes in ANCHORS.items():
            outputs = page.evaluate(f"() => OUTPUTS['{pillar}']")
            by_code = {o["code"]: o for o in outputs}
            for code, expected_num in codes.items():
                out = by_code.get(code)
                if out is None:
                    fails.append(f"{pillar}/{code}: not found in live OUTPUTS array")
                    continue
                result = page.evaluate(
                    "([pillar, out]) => extractCanonicalOutputBlock(pillar, out)",
                    [pillar, out],
                )
                checked += 1
                if expected_num is None:
                    # Step 3 authored real specs for all 8 codes that were
                    # null at Step 0 — expect RESOLVED + substantive content
                    # OR (for any future null code with no authored spec
                    # yet) the non-fabricating status record. Never a
                    # spurious match against the front-matter status board.
                    status = page.evaluate(f"() => getCanonicalSpecStatus('{pillar}','{code}')")
                    is_authored = status == "RESOLVED" and "Legal basis:" in result and len(result) > 500
                    is_status_record = "CANONICAL SPECIFICATION STATUS" in result and "No dedicated canonical specification is currently defined" in result
                    if not (is_authored or is_status_record):
                        fails.append(f"{pillar}/{code}: expected authored spec (RESOLVED) or non-fabricating status record, got status={status!r} text={result[:80]!r}")
                else:
                    expected_header = f"OUTPUT {expected_num:02d}  ·"
                    if not result.startswith(expected_header) and not result.lstrip().startswith(expected_header):
                        fails.append(
                            f"{pillar}/{code}: expected to start with {expected_header!r}, got: {result[:80]!r}"
                        )

        print(f"CHECKED: {checked} outputs across {len(ANCHORS)} pillars")
        print(f"FAILURES: {len(fails)}")
        for f in fails:
            print("  FAIL:", f)
        print("page errors:", errors)
        browser.close()

        ok = not fails and not errors
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
