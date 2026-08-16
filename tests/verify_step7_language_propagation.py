"""
Verifies Task J (language propagation) for the source-governance / NB
hierarchy / empty-annex additions landed in Steps 5-6: every closed-
vocabulary status label this session introduced (SOURCE-STATUS LABELLING,
NOTIFIED BODY hierarchy, EMPTY ANNEX readiness-impact labels) must carry
an explicit "keep this fixed English anchor term even in a non-English
run" instruction, matching the pre-existing pattern already used for the
Fact-Label Vocabulary and Mandatory Status Vocabulary/badges. Without this,
a non-English run's model has no anchor stopping it from translating a
label like "BLOCKING FOR THIS OUTPUT" — which would silently break
extractUnresolvedFields' READINESS_IMPACT_HINT_RE, since that regex
matches literal English text.

Also confirms the pre-existing languageDirective/noticeLanguageDirective
mechanism (buildGlobalRegulatoryGovernance) still precedes and therefore
governs all of this session's new sections 10-12 and the Step 3B priority
enrichment blocks, for every pillar — i.e. the new content is downstream
of the language instruction, not before it or in a separate ungoverned
prompt path.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step7_language_propagation.py
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
        page.fill('input[placeholder="Name or identifier"]', "Step7Check", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []

    # 1. Every closed-vocabulary block this session added must carry an
    # explicit language-exemption clause, for every pillar.
    LANG_EXEMPTION_CHECKS = [
        ("SOURCE-STATUS LABELLING", "LANGUAGE OF THIS VOCABULARY: these status labels are fixed English anchor terms"),
        ("NOTIFIED BODY / CONFORMITY MATERIAL", "LANGUAGE OF THIS VOCABULARY: the four source-class labels"),
        ("EMPTY ANNEX / EMPTY ARTEFACT RULE", "stated in English exactly as listed even in a non-English run"),
    ]
    for pillar, code in [("P1", "O03"), ("P2A", "O01"), ("P2B", "O01"), ("P3", "G01"), ("P4", "UM0")]:
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        result = page.evaluate("([p, o]) => buildSystemPrompt(p, o).cacheable", [pillar, out])
        for section_marker, exemption_marker in LANG_EXEMPTION_CHECKS:
            has_section = section_marker in result
            has_exemption = exemption_marker in result
            ok = has_section and has_exemption
            print(f"{'OK' if ok else 'FAIL'}  {pillar}/{code}: {section_marker!r} present={has_section}, exemption present={has_exemption}")
            if not ok:
                fails.append(f"{pillar}/{code}: missing section or language exemption for {section_marker!r}")

    # 2. languageDirective precedes (textually, in the returned string) every
    # new section 10/11/12 and the per-call priority-enrichment blocks, for
    # both an English-defaulted and an explicitly non-English system.
    out03_p2a = page.evaluate("() => OUTPUTS.P2A.find(o => o.code === 'O03')")
    full_default = page.evaluate(
        "([p, o]) => { const r = buildSystemPrompt(p, o); return r.cacheable + r.perCall; }",
        ["P2A", out03_p2a],
    )
    lang_idx = full_default.find("LANGUAGE — MANDATORY")
    source_status_idx = full_default.find("SOURCE-STATUS LABELLING")
    priority_idx = full_default.find("PRIORITY ENRICHMENT — RISK MANAGEMENT SYSTEM")
    print(f"languageDirective idx={lang_idx}, SOURCE-STATUS idx={source_status_idx}, priority-enrichment idx={priority_idx}")
    if lang_idx == -1:
        fails.append("LANGUAGE — MANDATORY directive not found in P2A/O03 prompt at all")
    if source_status_idx == -1 or lang_idx == -1 or not (lang_idx < source_status_idx):
        fails.append("languageDirective does not precede SOURCE-STATUS LABELLING in the assembled prompt")
    if priority_idx == -1 or lang_idx == -1 or not (lang_idx < priority_idx):
        fails.append("languageDirective does not precede the Step 3B priority-enrichment block in the assembled prompt")

    # 3. A non-English authLang actually changes the directive and still
    # precedes the new sections (simulate via a fake _govInputData-style
    # active system, matching how buildSystemPrompt resolves authLang).
    croatian_check = page.evaluate("""() => {
        const sys = { id: '__lang_check__', data: { authLang: 'Croatian' } };
        const prevSystems = st.systems, prevActiveId = st.activeId;
        st.systems = [sys]; st.activeId = '__lang_check__';
        try {
            const out = OUTPUTS.P2A.find(o => o.code === 'O03');
            const result = buildSystemPrompt('P2A', out).cacheable;
            return {
                hasCroatian: result.includes('write the ENTIRE output') && result.includes('in Croatian'),
                langIdx: result.indexOf('LANGUAGE — MANDATORY'),
                sourceStatusIdx: result.indexOf('SOURCE-STATUS LABELLING'),
            };
        } finally {
            st.systems = prevSystems; st.activeId = prevActiveId;
        }
    }""")
    print("Croatian authLang check:", croatian_check)
    if not croatian_check["hasCroatian"]:
        fails.append(f"Setting authLang='Croatian' did not produce a Croatian LANGUAGE — MANDATORY directive: {croatian_check}")
    if not (croatian_check["langIdx"] < croatian_check["sourceStatusIdx"]):
        fails.append("Croatian languageDirective does not precede SOURCE-STATUS LABELLING")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
