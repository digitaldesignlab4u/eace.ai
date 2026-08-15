"""
Verifies the CANONICAL SPEC MAPPING FAILURE safeguard added on top of the
Step 0 fix (extractCanonicalOutputBlock, index.html): for a P2A/P2B output
with a declared (non-null) canonical anchor, failing to resolve that anchor
at runtime must be a BLOCKING error (thrown, recorded in
CANONICAL_SPEC_MAPPING_FAILURES, status set to MISSING) rather than a
silent fall-through to the old fuzzy candidate search — that fall-through
is exactly what caused the Step 0 mismatch in the first place, so it must
never happen again for a declared anchor.

Checks two things live in a headless browser:
1. The healthy path: a real anchor (P2A O03) resolves and is marked
   MAPPED; a declared no-dedicated-section gap (P2A O25) returns the
   graceful fallback and is marked NO_DEDICATED_SECTION; no failures are
   recorded against the real, unmodified canonical text.
2. The failure path: with the P2A O03 anchor header temporarily corrupted
   (via a monkey-patched getCanonicalFullText wrapper, not by touching the
   frozen OUTPUT_CANONICAL_ANCHORS map), extraction must throw with the
   "CANONICAL SPEC MAPPING FAILURE — EXECUTION BLOCKED" message, record one
   failure with the right pillar/code, and set status to MISSING.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_mapping_safeguard.py
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
        page.fill('input[placeholder="Name or identifier"]', "SafeguardCheck", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    # 1. Real anchors should end up MAPPED after resolution, gaps NO_DEDICATED_SECTION.
    r1 = page.evaluate("""() => {
        extractCanonicalOutputBlock('P2A', OUTPUTS.P2A.find(o=>o.code==='O03'));
        return {
          mapped: getCanonicalSpecStatus('P2A','O03'),
          gap: getCanonicalSpecStatus('P2A','O25'),
          gapReturnedText: extractCanonicalOutputBlock('P2A', OUTPUTS.P2A.find(o=>o.code==='O25')).slice(0,60),
          failuresSoFar: CANONICAL_SPEC_MAPPING_FAILURES.length,
        };
    }""")
    print("Real-anchor status check:", r1)
    assert r1["mapped"] == "MAPPED", r1
    assert r1["gap"] == "NO_DEDICATED_SECTION", r1
    assert "NO DEDICATED CANONICAL SECTION FOUND" in r1["gapReturnedText"], r1
    assert r1["failuresSoFar"] == 0, "no real anchor should be broken right now"

    # 2. Simulate a broken anchor (declared anchor whose header can't be found)
    #    by calling the function against a fabricated pillar name that reuses
    #    the P2A canonical text but is NOT in OUTPUT_CANONICAL_ANCHORS, using
    #    a monkey-patched temporary anchor map entry via a non-frozen probe.
    #    Since OUTPUT_CANONICAL_ANCHORS is Object.freeze()'d (by design, so
    #    production code can't tamper with it), we instead unit-test the
    #    exact failure branch by calling extractCanonicalOutputBlock with an
    #    out.code that IS declared (O03) but temporarily feeding it a
    #    canonical text with that header removed, via a throwaway pillar
    #    entry added to CANONICAL_PROMPTS at runtime (test-only mutation of
    #    a page-global, not of the frozen anchor map).
    r2 = page.evaluate("""() => {
        // Register a fake pillar 'P2A' clone whose canonical text has the
        // OUTPUT 03 header text corrupted, then clear the cache so
        // getCanonicalFullText re-decodes lazily... simplest: monkey-patch
        // getCanonicalFullText itself for this one call via a wrapper.
        const realGetFull = getCanonicalFullText;
        window.getCanonicalFullText = function(pillar){
          const t = realGetFull(pillar);
          return pillar==='P2A' ? t.replace('\\nOUTPUT 03  ·', '\\nOUTPUT ZZ  ·') : t;
        };
        let threw = false, msg = '';
        try {
          extractCanonicalOutputBlock('P2A', OUTPUTS.P2A.find(o=>o.code==='O03'));
        } catch(e) {
          threw = true; msg = e.message;
        }
        window.getCanonicalFullText = realGetFull;
        return {
          threw, msg: msg.slice(0,200),
          status: getCanonicalSpecStatus('P2A','O03'),
          failures: CANONICAL_SPEC_MAPPING_FAILURES.length,
          lastFailure: CANONICAL_SPEC_MAPPING_FAILURES[CANONICAL_SPEC_MAPPING_FAILURES.length-1],
        };
    }""")
    print("Simulated broken-anchor check:", r2)
    assert r2["threw"] is True, r2
    assert "CANONICAL SPEC MAPPING FAILURE — EXECUTION BLOCKED" in r2["msg"], r2
    assert r2["status"] == "MISSING", r2
    assert r2["failures"] == 1, r2
    assert r2["lastFailure"]["pillar"] == "P2A" and r2["lastFailure"]["outputCode"] == "O03", r2

    print("ALL SAFEGUARD CHECKS PASSED")
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if not errors else 1)
