"""
Task I — field-propagation regression. Enumerates every field ID from the
three live intake schemas (MASTER_GROUPS + MASTER_GROUPS_EXT2 — the Engine
Hub intake form; FIELD_SCHEMA — the System Workspace "Master Profile" tab;
ORG_PROFILE_SCHEMA — the Organisation Profile, which reaches generation via
ORG_FALLBACK_COMPOSERS/applyOrgLiveFallback rather than being read directly)
and, for each one, sets a unique sentinel value on a synthetic system, calls
buildIntakeContext (the actual function that serializes the "SYSTEM PROFILE
— USER-SUPPLIED INPUT" block every generation prompt receives) via
getExecutionInputData(), and checks whether the sentinel value reaches the
assembled text — i.e. tests actual execution-context resolution, not just
whether the field renders in a UI form.

This test is the live-verification counterpart to the static analysis done
this session (tests/README.md and the implementation report document the
findings): buildIntakeContext previously read only ~84 distinct field
names, while the two live intake UIs between them define ~178 (MASTER_GROUPS)
and ~115 (FIELD_SCHEMA) field IDs, many under different names for the same
underlying regulatory fact (e.g. sysDesc/sysDescription, countryDeploy/
deploymentCountries, provName/orgName, nis2Provider/nisEntityProvider).
This session added alias-fallback resolution to the existing lines (prefer
the original field, fall back to the newer/alternate name) and net-new
lines for genuinely new facts, plus ten new ORG_FALLBACK_COMPOSERS entries
for previously-orphaned Organisation Profile legal-identity/governance
fields (orgLegal/orgTaxId/orgVatId/orgEuid/orgLei/orgWebsite/gdprLead/
aiGovernanceOwner/boardApproval/policyFramework).

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step8_field_propagation.py
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

# Fields intentionally excluded from propagation testing: pure internal
# bookkeeping/session state with no regulatory content of their own
# (never meant to reach a generation prompt).
INTENTIONALLY_EXCLUDED = {
    'updatedAt', 'updatedBy', 'executionId',
}

# Fields whose buildIntakeContext line renders a boolean (Yes/No) rather
# than echoing the raw value — a string sentinel would never appear
# literally in the output even though the field genuinely propagates, so
# these are tested with True instead of a string sentinel and the check is
# "does the line appear at all", not "does the sentinel string appear".
BOOL_FIELDS = {
    'continuousLearning', 'explainability', 'euEstablished', 'crossBorder',
    'gpai', 'fineTune', 'zdr', 'isGpai', 'gpaiCoPSignatory', 'personalData',
    'specialCategories', 'personalDataTraining', 'adm', 'cookies',
    'previousConformity', 'priorIncidents', 'priorRegulatory', 'r50Interacts',
    'r50Emotion', 'r50Biometric', 'r50Synthetic', 'r50Deepfake', 'r50Workers',
    'priorNearMisses', 'childrenData', 'communicationsMetadata', 'profiling',
    'qmsImplemented', 'internalModel', 'thirdPartyModel', 'gpaiDependency',
    'isGpaiModel', 'hasSupplyChain', 'internetRequired', 'offlineCapability',
    'apiExposure', 'exemResearch', 'exemMilitary', 'exemPersonal',
    'exemOpenSource', 'exemNone', 'employeesAffected', 'consumersAffected',
    'childrenAffected', 'vulnerableAffected', 'specialCategories',
}
# criticalInfra and priorAudit accept either a bool OR a select-string value
# in this codebase (two historical field variants share the id/concept) —
# tested with True, matching the boolean branch of their dual-typed lines.
BOOL_OR_SELECT_FIELDS = {'criticalInfra', 'priorAudit'}

# Dependent detail fields that only appear in the output when their parent
# flag is also set (matching the pre-existing pattern for e.g.
# crossBorder/crossBorderSpec) — tested with the parent set alongside them.
DEPENDENT_ON = {
    'crossBorderSpec': 'crossBorder',
    'specialCategoriesSpec': 'specialCategories',
    'gpaiModel': 'gpai',
    'finetuningDesc': 'fineTune',
}

# Fields that legitimately reach generation through a different prompt
# function than buildIntakeContext (documented at the point they're read):
# noticeLanguages is read directly from _govInputData inside
# buildGlobalRegulatoryGovernance's noticeLanguageDirective (Art. 50 notice
# language is deliberately independent of the document-language/intake
# narrative — see CLAUDE.md). Verified separately below, not via
# buildIntakeContext text.
OTHER_PATH_FIELDS = {'noticeLanguages'}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "FieldPropCheck", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    result = page.evaluate("""(args) => {
        const { excluded, boolFields, boolOrSelectFields, dependentOn, otherPathFields } = args;
        const masterIds = [];
        MASTER_GROUPS.concat(MASTER_GROUPS_EXT2||[]).forEach(g => (g.fields||[]).forEach(f => masterIds.push(f.id)));
        const fieldSchemaIds = Object.keys(FIELD_SCHEMA||{});
        const orgIds = Object.keys(ORG_PROFILE_SCHEMA||{});

        const allSystemFieldIds = [...new Set([...masterIds, ...fieldSchemaIds])]
            .filter(id => !excluded.includes(id) && !otherPathFields.includes(id));
        const allOrgFieldIds = orgIds.filter(id => !excluded.includes(id));

        // Save real state to restore afterwards.
        const prevSystems = st.systems, prevActiveId = st.activeId, prevData = st.data;
        const prevOrgProfile = JSON.parse(JSON.stringify(WORKSPACE.orgProfile || {}));

        const results = { systemFields: [], orgFields: [], duplicates: [] };

        // 1. Per-system field IDs (MASTER_GROUPS + FIELD_SCHEMA union): set
        // one at a time (plus its dependency parent, where one exists) on
        // an isolated synthetic system, call
        // getExecutionInputData()->buildIntakeContext. Boolean-typed fields
        // are set to `true` and checked for ANY output-text change vs a
        // clean baseline (their line renders Yes/No, never the sentinel
        // itself); everything else is set to a unique string sentinel and
        // checked for literal presence.
        for (const fieldId of allSystemFieldIds) {
            const isBool = boolFields.includes(fieldId) || boolOrSelectFields.includes(fieldId);
            const sentinel = 'SENTINEL_' + fieldId + '_9f3e';
            const sys = { id: '__prop_check__', name: 'PropCheck', data: {}, profile: {} };
            const setVal = isBool ? true : sentinel;
            sys.data[fieldId] = setVal;
            sys.profile[fieldId] = setVal;
            const parent = dependentOn[fieldId];
            if (parent) { sys.data[parent] = true; sys.profile[parent] = true; }
            st.systems = [sys];
            st.activeId = '__prop_check__';
            st.data = Object.assign({}, sys.data);
            WORKSPACE.orgProfile = {};
            let text = '';
            let baselineText = '';
            let errorMsg = null;
            try {
                const d = getExecutionInputData();
                text = buildIntakeContext(d, 'P2A');
                if (isBool) {
                    const baselineSys = { id: '__prop_check_base__', name: 'Base', data: {}, profile: {} };
                    st.systems = [baselineSys]; st.activeId = '__prop_check_base__'; st.data = {};
                    const bd = getExecutionInputData();
                    baselineText = buildIntakeContext(bd, 'P2A');
                }
            } catch (e) {
                errorMsg = String(e && e.message || e);
            }
            const propagated = isBool ? (text.length > 0 && text !== baselineText) : text.includes(sentinel);
            results.systemFields.push({ fieldId, propagated, error: errorMsg });
        }

        // 2. Organisation Profile field IDs: set on WORKSPACE.orgProfile
        // (no per-system value at all), confirm the live-fallback path
        // (applyOrgLiveFallback / ORG_FALLBACK_COMPOSERS) surfaces it,
        // either under its own name or via a composer into a different
        // per-system field name (e.g. orgName -> provName).
        for (const fieldId of allOrgFieldIds) {
            const sentinel = 'SENTINEL_ORG_' + fieldId + '_9f3e';
            const sys = { id: '__prop_check_org__', name: 'PropCheckOrg', data: {}, profile: {} };
            st.systems = [sys];
            st.activeId = '__prop_check_org__';
            st.data = {};
            WORKSPACE.orgProfile = Object.assign({}, ORG_PROFILE_SCHEMA, { [fieldId]: sentinel });
            let text = '';
            let errorMsg = null;
            let fallbackFieldName = null;
            try {
                const d = getExecutionInputData();
                // Which key(s) actually carry the sentinel after live-fallback?
                Object.keys(d || {}).forEach(k => { if (d[k] === sentinel) fallbackFieldName = k; });
                text = buildIntakeContext(d, 'P2A');
            } catch (e) {
                errorMsg = String(e && e.message || e);
            }
            results.orgFields.push({
                fieldId,
                propagated: text.includes(sentinel),
                fallbackFieldName,
                error: errorMsg,
            });
        }

        // 3. noticeLanguages: different, deliberate path (Art. 50 notice
        // language independent of document-language intake) — verify via
        // buildGlobalRegulatoryGovernance's noticeLanguageDirective instead
        // of buildIntakeContext.
        {
            const sentinel = 'SENTINEL_ORG_noticeLanguages_9f3e';
            const sys = { id: '__prop_check_notice__', name: 'PropCheckNotice', data: { noticeLanguages: [sentinel] }, profile: {} };
            st.systems = [sys]; st.activeId = '__prop_check_notice__'; st.data = { noticeLanguages: [sentinel] };
            WORKSPACE.orgProfile = {};
            let govText = '';
            let errorMsg = null;
            try { govText = buildGlobalRegulatoryGovernance('P2A'); }
            catch (e) { errorMsg = String(e && e.message || e); }
            results.noticeLanguages = { propagated: govText.includes(sentinel), error: errorMsg };
        }

        // Restore real state.
        st.systems = prevSystems; st.activeId = prevActiveId; st.data = prevData;
        WORKSPACE.orgProfile = prevOrgProfile;

        return results;
    }""", {
        "excluded": list(INTENTIONALLY_EXCLUDED),
        "boolFields": list(BOOL_FIELDS),
        "boolOrSelectFields": list(BOOL_OR_SELECT_FIELDS),
        "dependentOn": DEPENDENT_ON,
        "otherPathFields": list(OTHER_PATH_FIELDS),
    })

    sys_results = result["systemFields"]
    org_results = result["orgFields"]

    sys_total = len(sys_results)
    sys_success = sum(1 for r in sys_results if r["propagated"])
    sys_fail = [r for r in sys_results if not r["propagated"]]

    org_total = len(org_results)
    org_success = sum(1 for r in org_results if r["propagated"])
    org_fail = [r for r in org_results if not r["propagated"]]
    org_via_fallback = [r for r in org_results if r["propagated"] and r["fallbackFieldName"] and r["fallbackFieldName"] != r["fieldId"]]
    org_via_own_name = [r for r in org_results if r["propagated"] and r["fallbackFieldName"] == r["fieldId"]]

    print("=" * 70)
    print("FIELD-PROPAGATION REGRESSION REPORT (Task I)")
    print("=" * 70)
    print(f"\nPer-system fields (MASTER_GROUPS + FIELD_SCHEMA union, excl. {sorted(INTENTIONALLY_EXCLUDED)}):")
    print(f"  Total tested:  {sys_total}")
    print(f"  Successful:    {sys_success}")
    print(f"  Failures:      {len(sys_fail)}")
    if sys_fail:
        print("  Failed field IDs:", ', '.join(r['fieldId'] for r in sys_fail))

    print(f"\nOrganisation Profile fields (via live fallback):")
    print(f"  Total tested:      {org_total}")
    print(f"  Successful:        {org_success}")
    print(f"  Failures:          {len(org_fail)}")
    print(f"  Via own field name: {len(org_via_own_name)}")
    print(f"  Via composer to a different per-system field name: {len(org_via_fallback)}")
    for r in org_via_fallback:
        print(f"    {r['fieldId']} -> {r['fallbackFieldName']}")
    if org_fail:
        print("  Failed org field IDs:", ', '.join(r['fieldId'] for r in org_fail))

    notice = result["noticeLanguages"]
    print(f"\nnoticeLanguages (separate path — buildGlobalRegulatoryGovernance): propagated={notice['propagated']} error={notice['error']}")

    fails = []
    # Allow a small, named tolerance: fields that are legitimately UI-only
    # display/derivation inputs rather than generation-context facts would
    # be listed here with justification if any turned up during triage.
    KNOWN_ACCEPTABLE_GAPS = set()

    for r in sys_fail:
        if r["fieldId"] not in KNOWN_ACCEPTABLE_GAPS:
            fails.append(f"System field {r['fieldId']!r} did not propagate to buildIntakeContext output (error={r['error']!r})")
    for r in org_fail:
        if r["fieldId"] not in KNOWN_ACCEPTABLE_GAPS:
            fails.append(f"Org field {r['fieldId']!r} did not propagate via live fallback (error={r['error']!r})")
    if not notice["propagated"]:
        fails.append(f"noticeLanguages did not propagate via buildGlobalRegulatoryGovernance (error={notice['error']!r})")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
