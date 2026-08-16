"""
Verifies the three-state CANONICAL SPEC MAPPING FAILURE safeguard
(extractCanonicalOutputBlock / buildOutputRegistry / execRun, index.html).

Corrected design (per explicit follow-up instruction after the first cut of
this safeguard conflated two different conditions):
  RESOLVED             — real canonical section found. Normal generation.
  MAPPING_FAILURE      — a dedicated canonical section IS expected (a
                          non-null anchor declared) but could not be
                          resolved at runtime. Genuine engine defect.
                          Blocks GENERATION OF THAT OUTPUT ONLY — never the
                          whole pillar's registry or run.
  NO_DEDICATED_SECTION — the catalogue intentionally has no canonical
                          section for this output yet. NOT an engine
                          failure, does NOT block anything, and must NOT
                          read as licence for the model to invent the
                          missing methodology — the fallback text must
                          explicitly forbid drafting a substantive artefact
                          and require a short status record instead. As of
                          Step 3, all 8 codes the Step 0 audit found in
                          this state now have a real ENGINE_AUTHORED_SPECS
                          entry and resolve RESOLVED — this test exercises
                          the fallback itself by temporarily removing one
                          authored entry, since no genuine gap remains in
                          the live catalogue to point at directly.

Checks, live in a headless browser:
1. Healthy path: a real anchor (P2A O03) resolves to RESOLVED; with P2A
   O25's Step 3 authored spec temporarily removed (restored immediately
   after), it returns the non-fabricating status-record fallback and is
   marked NO_DEDICATED_SECTION; zero failures recorded against the real,
   unmodified canonical text.
2. Failure path: with the P2A O03 anchor header temporarily corrupted
   (monkey-patched getCanonicalFullText, not the frozen anchor map),
   extraction throws "CANONICAL SPEC MAPPING FAILURE — EXECUTION BLOCKED",
   records one failure, sets status MAPPING_FAILURE.
3. Isolation: with only P2A O03's anchor corrupted, buildOutputRegistry('P2A')
   still successfully registers every OTHER P2A output — O03 alone is
   excluded, registry.mappingFailureOutputs contains exactly ['O03'], and
   registry.packageStatus reports PARTIALLY_INCOMPLETE — confirming one
   broken mapping cannot take down the rest of the pillar's outputs.

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

    # 1. Real anchors should resolve RESOLVED. All 8 codes that were
    #    NO_DEDICATED_SECTION at Step 0 now have a Step 3 engine-authored
    #    spec (ENGINE_AUTHORED_SPECS) and resolve RESOLVED too — so the
    #    genuine "still a gap" fallback is exercised here by temporarily
    #    removing one authored entry (ENGINE_AUTHORED_SPECS's outer object
    #    is frozen, but its inner P2A/P2B objects are plain and mutable —
    #    this deletes then restores a nested key, it does not touch the
    #    frozen OUTPUT_CANONICAL_ANCHORS map at all) rather than asserting
    #    against a code that no longer represents the fallback path.
    r1 = page.evaluate("""() => {
        extractCanonicalOutputBlock('P2A', OUTPUTS.P2A.find(o=>o.code==='O03'));
        const savedSpec = ENGINE_AUTHORED_SPECS.P2A.O25;
        delete ENGINE_AUTHORED_SPECS.P2A.O25;
        delete CANONICAL_SPEC_STATUS['P2A:O25']; // clear cached RESOLVED from earlier in this session
        const gapText = extractCanonicalOutputBlock('P2A', OUTPUTS.P2A.find(o=>o.code==='O25'));
        const gapStatus = getCanonicalSpecStatus('P2A','O25');
        ENGINE_AUTHORED_SPECS.P2A.O25 = savedSpec; // restore — must not leak into later real usage
        return {
          resolved: getCanonicalSpecStatus('P2A','O03'),
          gap: gapStatus,
          gapReturnedText: gapText,
          failuresSoFar: CANONICAL_SPEC_MAPPING_FAILURES.length,
        };
    }""")
    print("Real-anchor / simulated-still-a-gap status check:", {k: (v[:80] + '...' if isinstance(v, str) and len(v) > 80 else v) for k, v in r1.items()})
    assert r1["resolved"] == "RESOLVED", r1
    assert r1["gap"] == "NO_DEDICATED_SECTION", r1
    assert "No dedicated canonical specification is currently defined" in r1["gapReturnedText"], r1
    assert "Do NOT draft the substantive artefact" in r1["gapReturnedText"], r1
    assert "Generate this output to the same rigour" not in r1["gapReturnedText"], "fallback must not invite fabrication: " + r1["gapReturnedText"]
    assert r1["failuresSoFar"] == 0, "no real anchor should be broken right now"

    # 2. Simulate a broken anchor (declared anchor whose header can't be found)
    #    via a monkey-patched getCanonicalFullText wrapper (test-only mutation
    #    of a page-global, not of the frozen OUTPUT_CANONICAL_ANCHORS map).
    r2 = page.evaluate("""() => {
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
    assert r2["status"] == "MAPPING_FAILURE", r2
    assert r2["failures"] == 1, r2
    assert r2["lastFailure"]["pillar"] == "P2A" and r2["lastFailure"]["outputCode"] == "O03", r2

    # 3. Isolation: buildOutputRegistry('P2A') with only O03 broken must still
    #    register every other P2A output; only O03 is excluded/flagged.
    r3 = page.evaluate("""() => {
        const realGetFull = getCanonicalFullText;
        window.getCanonicalFullText = function(pillar){
          const t = realGetFull(pillar);
          return pillar==='P2A' ? t.replace('\\nOUTPUT 03  ·', '\\nOUTPUT ZZ  ·') : t;
        };
        delete _outputRegistryCache['P2A']; // force rebuild against corrupted text
        const registry = buildOutputRegistry('P2A');
        window.getCanonicalFullText = realGetFull;
        delete _outputRegistryCache['P2A']; // discard corrupted registry, don't leak into later real usage
        return {
          mappingFailureOutputs: registry.mappingFailureOutputs,
          packageStatus: registry.packageStatus,
          hasO03: !!registry.outputs['O03'],
          hasO01: !!registry.outputs['O01'],
          hasO11: !!registry.outputs['O11'],
          totalResolved: Object.keys(registry.outputs).length,
        };
    }""")
    print("Registry isolation check:", r3)
    assert r3["mappingFailureOutputs"] == ["O03"], r3
    assert r3["packageStatus"] == "PARTIALLY_INCOMPLETE — ENGINE INTEGRITY ISSUE", r3
    assert r3["hasO03"] is False, r3
    assert r3["hasO01"] is True and r3["hasO11"] is True, "other P2A outputs must still resolve: " + str(r3)
    assert r3["totalResolved"] == 32, r3  # 33 P2A entries minus the one blocked (O03)

    print("ALL SAFEGUARD CHECKS PASSED")
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if not errors else 1)
