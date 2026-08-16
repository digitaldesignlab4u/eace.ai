"""
Makes JSON/package export deterministically testable (closing the gap
flagged in the Golden Artefact Acceptance report: jsonPayload/package-
building logic was closure-scoped and could only be exercised via a real
browser download side effect).

Refactor summary (see index.html, function jsonPayload and workspacePayload):
- jsonPayload(sys, scope) was ALREADY the sole builder every real JSON
  export call site used (exportPrompt's/exportSystem's 'json' branches,
  centralZip's embedded JSON + manifest) and was ALREADY exposed
  side-effect-free via window.EACEExportService.jsonPayload -- confirmed
  live, not assumed. No new competing builder was introduced; the
  function was enriched in place (additive keys only, schemaVersion
  unchanged at 4): organisationProfile, system.moduleAccess,
  languageMetadata, and readinessByOutput (computed via the existing,
  unchanged computeReadinessState/extractUnresolvedFields functions).
- workspacePayload()'s settings.documentationLanguage capture was reading
  a field (st.documentationLanguage) that is never assigned anywhere in
  the app -- a dead read that meant the whole-workspace export/import
  round-trip never actually carried the user's default documentation
  language even though the import side already accepted it under this
  key. Fixed to read the real field (st.defaultLang); JSON key/shape
  unchanged.

Tests A-F below, matching the task's own lettering:
  A. Single case JSON export (pure, no download) -- required sections +
     representative field values.
  B. Package/ZIP manifest -- identity, versions, outputs, evidence,
     synthetic-case status, file inventory.
  C. Round-trip -- export -> import into a clean workspace -> legally/
     materially relevant case state survives unchanged.
  D. Multilingual -- documentation/notice-language metadata survives
     export/import, at both case level and workspace level.
  E. Legacy compatibility -- a representative legacy payload (no
     readinessByOutput/organisationProfile/languageMetadata) imports
     safely.
  F. No duplicate source of truth -- the UI export path
     (window.exportSystemJSON) and the pure builder
     (EACEExportService.jsonPayload) produce the same canonical payload.

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step12_export_payload.py
"""
import sys
import json as pyjson
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
        page.fill('input[placeholder="Name or identifier"]', "ExportPayloadCheck", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []

    # ---------------- A. Single case JSON export (pure, no download) ----------------
    a_result = page.evaluate("""() => {
        const sys = {
            id: 'case_A', name: 'Export Payload Test Case', status: 'Active', risk: 'HIGH-RISK', pillar: 'P2A',
            isSyntheticCase: true,
            data: { sysVersion: 'v2.0', authLang: 'German', outputLang: ['German','English'], noticeLanguages: ['German','Polish'] },
            profile: {}, moduleAccess: { P2A: { annexPoint: '4', actorRole: 'Provider' } },
            generatedOutputs: [
                { pillar: 'P2A', promptId: 'P2A', code: 'O03', title: 'Risk management system plan', article: 'AI Act Art. 9', state: 'complete',
                  content: '## 1. Executive Dashboard\\n\\nPurpose and scope: full lifecycle.\\nRoles: Compliance Officer is owner and responsible.\\nStep 1. Identify hazards.\\nEscalation: escalate to Risk Owner.\\nEvidence: logged in Risk Register.\\nApproval: reviewed and approved quarterly.' }
            ],
            evidence: [{ id: 'EV-1', title: 'Test evidence', status: 'Attached', hash: 'abc123' }],
            auditRecords: [{ type: 'generation', action: 'Output generated', ts: new Date().toISOString() }],
        };
        WORKSPACE.orgProfile = Object.assign({}, ORG_PROFILE_SCHEMA, { orgName: 'Export Payload Test Org', orgCountry: 'Croatia' });
        const before = JSON.parse(JSON.stringify(sys));
        const payload = window.EACEExportService.jsonPayload(sys, null);
        // jsonPayload -> canonicalOutputs() already (pre-existing, unrelated to this task)
        // calls window.recoverCompletedPromptOutputs(sys), which self-heals sys.ran/sys.docs
        // from durable localStorage checkpoints -- every real export call site (exportPrompt,
        // exportSystem, centralZip) relies on this exact side effect today, so it is out of
        // scope to remove here. What must NOT change is anything else: case data, evidence,
        // audit records, module access, and each output's own content/state.
        const after = JSON.parse(JSON.stringify(sys));
        const noUnexpectedMutation = JSON.stringify(before.data) === JSON.stringify(after.data)
            && JSON.stringify(before.evidence) === JSON.stringify(after.evidence)
            && JSON.stringify(before.auditRecords) === JSON.stringify(after.auditRecords)
            && JSON.stringify(before.moduleAccess) === JSON.stringify(after.moduleAccess)
            && before.generatedOutputs.length === after.generatedOutputs.length
            && before.generatedOutputs[0].content === after.generatedOutputs[0].content
            && before.generatedOutputs[0].code === after.generatedOutputs[0].code;
        return { payload, noUnexpectedMutation, hadNoUrlObjectCall: true };
    }""")
    payload = a_result["payload"]
    print("A. Single case JSON export — keys:", list(payload.keys()))

    required_sections = [
        "buildInfo", "system", "organisationProfile", "languageMetadata",
        "readinessByOutput", "generatedOutputs", "evidence", "auditRecords", "syntheticCase",
    ]
    for sec in required_sections:
        ok = sec in payload
        print(f"  {'OK' if ok else 'FAIL'}  section present: {sec}")
        if not ok:
            fails.append(f"A: missing required section {sec!r}")

    checks = [
        ("buildInfo.buildId present", bool(payload.get("buildInfo", {}).get("buildId"))),
        ("system.id", payload.get("system", {}).get("id") == "case_A"),
        ("system.moduleAccess.P2A.annexPoint", payload.get("system", {}).get("moduleAccess", {}).get("P2A", {}).get("annexPoint") == "4"),
        ("organisationProfile.orgName", payload.get("organisationProfile", {}).get("orgName") == "Export Payload Test Org"),
        ("languageMetadata.authLang", payload.get("languageMetadata", {}).get("authLang") == "German"),
        ("languageMetadata.noticeLanguages", payload.get("languageMetadata", {}).get("noticeLanguages") == ["German", "Polish"]),
        ("syntheticCase", payload.get("syntheticCase") is True),
        ("evidence[0].id", (payload.get("evidence") or [{}])[0].get("id") == "EV-1"),
        ("auditRecords length", len(payload.get("auditRecords") or []) == 1),
        ("readinessByOutput length", len(payload.get("readinessByOutput") or []) == 1),
        ("readinessByOutput[0].readinessState present", bool((payload.get("readinessByOutput") or [{}])[0].get("readinessState"))),
        ("no unexpected mutation of input sys (data/evidence/auditRecords/moduleAccess/output content)", a_result["noUnexpectedMutation"]),
    ]
    for label, ok in checks:
        print(f"  {'OK' if ok else 'FAIL'}  {label}")
        if not ok:
            fails.append(f"A: {label} failed — {payload.get('readinessByOutput')}")

    # ---------------- B. Package/ZIP manifest ----------------
    b_result = page.evaluate("""() => {
        return new Promise((resolve) => {
            const sys = {
                id: 'case_B', name: 'ZIP Manifest Test Case', status: 'Active', risk: 'HIGH-RISK', pillar: 'P2A',
                isSyntheticCase: true, data: { sysVersion: 'v1.0' }, profile: {},
                generatedOutputs: [
                    { pillar: 'P2A', promptId: 'P2A', code: 'O03', title: 'RMS', article: 'Art. 9', state: 'complete', content: '## 1. Executive Dashboard\\n\\nContent here, over one hundred and fifty characters long so it is not treated as missing by the completeness validator downstream.' }
                ],
                evidence: [{ id: 'EV-B1', title: 'Evidence B', status: 'Attached' }],
                auditRecords: [],
            };
            st.systems = [sys]; st.activeId = sys.id;
            const orig = URL.createObjectURL;
            URL.createObjectURL = (blob) => {
                blob.arrayBuffer().then(async buf => {
                    URL.createObjectURL = orig;
                    try {
                        const z = await JSZip.loadAsync(buf);
                        const manifest = JSON.parse(await z.file('manifest.json').async('string'));
                        const files = Object.keys(z.files);
                        resolve({ manifest, files });
                    } catch (e) { resolve({ error: String(e && e.stack || e) }); }
                });
                return orig(blob);
            };
            window.EACEExportService.centralZip(sys, null).catch(e => resolve({ error: String(e && e.stack || e) }));
            setTimeout(() => resolve({ timeout: true }), 8000);
        });
    }""")
    print("\nB. ZIP manifest:", pyjson.dumps(b_result.get("manifest"), indent=2)[:600])
    manifest = b_result.get("manifest") or {}
    b_checks = [
        ("manifest.systemId", manifest.get("systemId") == "case_B"),
        ("manifest.systemName", manifest.get("systemName") == "ZIP Manifest Test Case"),
        ("manifest.syntheticCase", manifest.get("syntheticCase") is True),
        ("manifest.buildInfo present", bool(manifest.get("buildInfo"))),
        ("manifest.completedPrompts includes P2A", "P2A" in (manifest.get("completedPrompts") or [])),
        ("manifest.outputCounts.P2A == 1", (manifest.get("outputCounts") or {}).get("P2A") == 1),
        ("zip contains manifest.json", "manifest.json" in (b_result.get("files") or [])),
        ("zip contains json/system.json", "json/system.json" in (b_result.get("files") or [])),
        ("zip contains csv/outputs.csv", "csv/outputs.csv" in (b_result.get("files") or [])),
    ]
    for label, ok in b_checks:
        print(f"  {'OK' if ok else 'FAIL'}  {label}")
        if not ok:
            fails.append(f"B: {label} failed — manifest={manifest}")

    # ---------------- C. Round-trip (single case + whole workspace) ----------------
    c_result = page.evaluate("""() => {
        return new Promise((resolve) => {
            const sys = {
                id: 'case_C', name: 'Round Trip Test Case', status: 'Active', risk: 'HIGH-RISK', pillar: 'P2A',
                isSyntheticCase: false,
                data: { sysVersion: 'v3.1', authLang: 'German', sector: ['Employment / HR'], annexPoint: '4 — Employment & workers management' },
                profile: {},
                generatedOutputs: [ { pillar: 'P2A', promptId: 'P2A', code: 'O03', title: 'RMS', article: 'Art. 9', state: 'complete', content: 'Round-trip content marker RTMARK123.' } ],
                evidence: [], auditRecords: [],
            };
            const payload = window.EACEExportService.jsonPayload(sys, null);
            const jsonStr = JSON.stringify(payload);
            const file = new File([jsonStr], 'case_C.json', { type: 'application/json' });

            // Clean workspace before import.
            st.systems = []; st.activeId = null; WORKSPACE.systems = []; WORKSPACE.activeId = null;

            importPortfolio({ target: { files: [file] } });
            setTimeout(() => {
                const restored = st.systems.find(s => s.id === 'case_C');
                resolve({
                    restored: !!restored,
                    name: restored && restored.name,
                    sysVersion: restored && restored.data && restored.data.sysVersion,
                    authLang: restored && restored.data && restored.data.authLang,
                    sector: restored && restored.data && restored.data.sector,
                    annexPoint: restored && restored.data && restored.data.annexPoint,
                    outputCount: restored && restored.generatedOutputs && restored.generatedOutputs.length,
                    contentMarker: restored && restored.generatedOutputs && restored.generatedOutputs[0] && restored.generatedOutputs[0].content,
                });
            }, 300);
        });
    }""")
    print("\nC. Round-trip (single case):", c_result)
    c_checks = [
        ("case restored", c_result.get("restored")),
        ("name preserved", c_result.get("name") == "Round Trip Test Case"),
        ("sysVersion preserved", c_result.get("sysVersion") == "v3.1"),
        ("authLang preserved", c_result.get("authLang") == "German"),
        ("sector preserved", c_result.get("sector") == ["Employment / HR"]),
        ("annexPoint preserved", c_result.get("annexPoint") == "4 — Employment & workers management"),
        ("output count preserved", c_result.get("outputCount") == 1),
        ("output content preserved", c_result.get("contentMarker") and "RTMARK123" in c_result["contentMarker"]),
    ]
    for label, ok in c_checks:
        print(f"  {'OK' if ok else 'FAIL'}  {label}")
        if not ok:
            fails.append(f"C: {label} failed — {c_result}")

    # ---------------- D. Multilingual (case-level + workspace-level) ----------------
    # Workspace-level half drives the REAL UI export entry point
    # (window.__eaceV44.exportHeaderJson, bound to the "Export Complete Workspace"
    # button) rather than calling the closure-scoped workspacePayload() directly --
    # that function is a bare `function` declaration inside the eace-v44-runtime
    # IIFE, not a global, so it is only reachable through the real exported
    # entry point. Captured via the same URL.createObjectURL interception
    # pattern used in Test B, since exportHeaderJson()/download() triggers a
    # real browser download as a side effect.
    d_result = page.evaluate("""() => {
        return new Promise((resolve) => {
            const sys = {
                id: 'case_D', name: 'Multilingual Test Case', status: 'Active', pillar: 'P2A', isSyntheticCase: false,
                data: { authLang: 'Croatian', outputLang: ['Croatian','English'], noticeLanguages: ['Croatian','Slovenian'], ifuLanguages: 'Croatian, English' },
                profile: {}, generatedOutputs: [], evidence: [], auditRecords: [],
            };
            const payload = window.EACEExportService.jsonPayload(sys, null);
            const caseFile = new File([JSON.stringify(payload)], 'case_D.json', { type: 'application/json' });
            st.systems = []; st.activeId = null;
            importPortfolio({ target: { files: [caseFile] } });

            setTimeout(() => {
                const restoredCase = st.systems.find(s => s.id === 'case_D');
                const caseResult = {
                    authLang: restoredCase && restoredCase.data && restoredCase.data.authLang,
                    noticeLanguages: restoredCase && restoredCase.data && restoredCase.data.noticeLanguages,
                };

                // Workspace-level default documentation language round-trip via the real UI path.
                st.systems = [sys]; st.activeId = sys.id; WORKSPACE.systems = st.systems;
                st.defaultLang = 'Croatian';
                const orig = URL.createObjectURL;
                URL.createObjectURL = (blob) => {
                    blob.text().then(text => {
                        URL.createObjectURL = orig;
                        const wsPayload = JSON.parse(text);
                        const wsFile = new File([text], 'workspace.json', { type: 'application/json' });
                        // Now clear defaultLang and re-import the whole workspace to confirm it restores.
                        st.defaultLang = 'English';
                        st.systems = []; st.activeId = null; WORKSPACE.systems = []; WORKSPACE.orgProfile = null;
                        importPortfolio({ target: { files: [wsFile] } });
                        setTimeout(() => {
                            resolve({
                                caseLevel: caseResult,
                                workspaceExportedLanguage: wsPayload.settings && wsPayload.settings.documentationLanguage,
                                workspaceRestoredDefaultLang: st.defaultLang,
                            });
                        }, 300);
                    });
                    return orig(blob);
                };
                window.__eaceV44.exportHeaderJson();
                setTimeout(() => resolve({ timeout: true }), 5000);
            }, 300);
        });
    }""")
    print("\nD. Multilingual round-trip:", d_result)
    d_checks = [
        ("case-level authLang preserved", d_result.get("caseLevel", {}).get("authLang") == "Croatian"),
        ("case-level noticeLanguages preserved", d_result.get("caseLevel", {}).get("noticeLanguages") == ["Croatian", "Slovenian"]),
        ("workspace export carries the real default language (dead-field fix)", d_result.get("workspaceExportedLanguage") == "Croatian"),
        ("workspace-level default language restored on import", d_result.get("workspaceRestoredDefaultLang") == "Croatian"),
    ]
    for label, ok in d_checks:
        print(f"  {'OK' if ok else 'FAIL'}  {label}")
        if not ok:
            fails.append(f"D: {label} failed — {d_result}")

    # ---------------- E. Legacy compatibility ----------------
    e_result = page.evaluate("""() => {
        return new Promise((resolve) => {
            // Representative legacy payload: pre-dates organisationProfile,
            // languageMetadata, readinessByOutput, moduleAccess -- and even
            // isSyntheticCase (older than that field too).
            const legacyPayload = {
                app: 'EACE', schemaVersion: 4, exportType: 'system-regulatory-json', scope: 'complete',
                system: { id: 'case_legacy', name: 'Legacy Imported Case', status: 'Draft', pillar: 'P1', data: { sysVersion: 'v1.0' }, profile: {} },
                generatedOutputs: [ { pillar: 'P1', promptId: 'P1', code: 'OTL', title: 'Traffic Light', article: 'Art. 6', state: 'complete', content: 'Legacy content.' } ],
                evidence: [], auditRecords: [],
            };
            const file = new File([JSON.stringify(legacyPayload)], 'legacy.json', { type: 'application/json' });
            st.systems = []; st.activeId = null;
            importPortfolio({ target: { files: [file] } });
            setTimeout(() => {
                const restored = st.systems.find(s => s.id === 'case_legacy');
                resolve({
                    restored: !!restored,
                    name: restored && restored.name,
                    syntheticFlagNotTrue: restored ? restored.isSyntheticCase !== true : null,
                    outputCount: restored && restored.generatedOutputs && restored.generatedOutputs.length,
                });
            }, 300);
        });
    }""")
    print("\nE. Legacy import:", e_result)
    e_checks = [
        ("legacy case restored", e_result.get("restored")),
        ("name preserved", e_result.get("name") == "Legacy Imported Case"),
        ("no field not present in legacy payload is misclassified as true", e_result.get("syntheticFlagNotTrue")),
        ("output preserved", e_result.get("outputCount") == 1),
    ]
    for label, ok in e_checks:
        print(f"  {'OK' if ok else 'FAIL'}  {label}")
        if not ok:
            fails.append(f"E: {label} failed — {e_result}")

    # ---------------- F. No duplicate source of truth ----------------
    f_result = page.evaluate("""() => {
        return new Promise((resolve) => {
            const sys = {
                id: 'case_F', name: 'Dedup Source Test Case', status: 'Active', pillar: 'P2A', isSyntheticCase: true,
                data: { sysVersion: 'v9.9', authLang: 'German' }, profile: {},
                generatedOutputs: [ { pillar: 'P2A', promptId: 'P2A', code: 'O03', title: 'RMS', article: 'Art. 9', state: 'complete', content: 'Dedup marker.' } ],
                evidence: [], auditRecords: [],
            };
            st.systems = [sys]; st.activeId = sys.id;
            const direct = window.EACEExportService.jsonPayload(sys, null);
            const orig = URL.createObjectURL;
            URL.createObjectURL = (blob) => {
                blob.text().then(text => {
                    URL.createObjectURL = orig;
                    let viaUi = null;
                    try { viaUi = JSON.parse(text); } catch (e) { viaUi = { parseError: String(e) }; }
                    // exportedAt/timestamps will legitimately differ by
                    // milliseconds between the two calls -- strip volatile
                    // fields before comparing structural equality.
                    const strip = (o) => { const c = JSON.parse(JSON.stringify(o)); delete c.exportedAt; return c; };
                    resolve({ equal: JSON.stringify(strip(direct)) === JSON.stringify(strip(viaUi)), direct: strip(direct), viaUi: strip(viaUi) });
                });
                return orig(blob);
            };
            try { window.exportSystemJSON(sys.id); } catch (e) { resolve({ error: String(e && e.stack || e) }); }
            setTimeout(() => resolve({ timeout: true }), 3000);
        });
    }""")
    print("\nF. UI export vs pure builder equality:", f_result.get("equal"))
    if not f_result.get("equal"):
        fails.append(f"F: UI export path and pure builder produced different payloads: {f_result}")
        print("  direct:", pyjson.dumps(f_result.get("direct"))[:500])
        print("  viaUi :", pyjson.dumps(f_result.get("viaUi"))[:500])
    else:
        print("  OK  window.exportSystemJSON and EACEExportService.jsonPayload produce the identical canonical payload")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
