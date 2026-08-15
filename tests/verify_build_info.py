"""
Verifies BUILD_INFO and isSyntheticCase propagation end-to-end, against the
*actual live* export entry points (not just source reading) -- this file's
window.X assignments get shadowed easily (see CLAUDE.md), so every check
here calls the real window.* function a user/button would trigger and
inspects the resulting blob, not an intermediate helper that might be dead
code by the time it runs.

Usage:
    python3 -m http.server 8899 &   # from the repo root
    python3 tests/verify_build_info.py [base_url]

Exits non-zero if any check fails or the page threw any error.
"""
import sys
import time
import json
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), "-", name, ("| " + detail if detail else ""))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
        page = browser.new_page(viewport={"width": 1300, "height": 1600})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        time.sleep(0.3)

        check("Application loads", "EACE" in page.inner_text("body"))

        if "ENTER WORKSPACE" in page.inner_text("body"):
            page.fill('input[placeholder="Name or identifier"]', "Verify", timeout=3000)
            page.click("text=ENTER WORKSPACE", timeout=3000)
            time.sleep(1)

        setup = page.evaluate("""() => {
            const OUT = (pillar, code, title, article, content) => ({
                pillar, promptId: pillar, code, title, article, cat: 'Core', state: 'complete', content
            });
            const outputs = [
                OUT('P1','OTL','Traffic Light Summary','AI Act Art. 6','## Traffic Light\\nResult: [HIGH-RISK] test content.'),
                OUT('P2A','O02','Provider obligations','AI Act Art. 16','# Provider\\n\\n| Field | Value |\\n|---|---|\\n| Risk | High |'),
            ];
            const real = createSystemObject({id:'sys_real_verify', name:'RealCase AI', generatedOutputs: outputs.map(o=>Object.assign({},o))});
            const synth = createSystemObject({id:'sys_synth_verify', name:'SynthCase AI', isSyntheticCase:true, generatedOutputs: outputs.map(o=>Object.assign({},o))});
            st.systems.push(real, synth);
            st.activeId = real.id;
            saveSystems();
            return {realId: real.id, synthId: synth.id};
        }""")
        real_id, synth_id = setup["realId"], setup["synthId"]

        flags = page.evaluate(
            """(ids) => {
            const r = st.systems.find(s=>s.id===ids.real);
            const s = st.systems.find(s=>s.id===ids.synth);
            return {realFlag: r.isSyntheticCase, synthFlag: s.isSyntheticCase};
        }""",
            {"real": real_id, "synth": synth_id},
        )
        check("New real case created, isSyntheticCase=false", flags["realFlag"] is False, str(flags["realFlag"]))
        check("New synthetic case created, isSyntheticCase=true", flags["synthFlag"] is True, str(flags["synthFlag"]))

        for sid, expect_banner, label in [
            (real_id, False, "Real case: NO synthetic banner in Overview"),
            (synth_id, True, "Synthetic case: synthetic banner present in Overview"),
        ]:
            page.evaluate(
                """(id) => {
                const s = st.systems.find(x=>x.id===id);
                sw.activeSystem = s; sw.tab='overview'; st.activeId = id;
            }""",
                sid,
            )
            page.evaluate("() => { renderSystemWorkspace(); }")
            time.sleep(0.1)
            html = page.evaluate("() => document.getElementById('sw-body') ? document.getElementById('sw-body').innerHTML : ''")
            has = "SYNTHETIC REGULATORY TEST CASE" in html
            check(label, has == expect_banner, "banner found=" + str(has))

        build_info = page.evaluate(
            "() => ({productVersion: BUILD_INFO.productVersion, buildId: BUILD_INFO.buildId, exportPackageVersion: BUILD_INFO.exportPackageVersion})"
        )
        print("BUILD_INFO:", build_info)

        # window.exportSystemJSON's live chain is EACEExportService.exportSystem ->
        # run -> exportOne -> fullJson -- several layers from the obvious same-named
        # function (see CLAUDE.md shadowing gotcha). Testing the real window.* call,
        # not fullJson() directly, is the point of this check.
        for sid, expect_synth, label in [
            (real_id, False, "JSON export (real, live window.exportSystemJSON path)"),
            (synth_id, True, "JSON export (synthetic, live window.exportSystemJSON path)"),
        ]:
            result = page.evaluate(
                """(id) => {
                return new Promise((resolve) => {
                    const orig = URL.createObjectURL;
                    URL.createObjectURL = (blob) => {
                        blob.text().then(text => { URL.createObjectURL = orig; try { resolve(JSON.parse(text)); } catch(e) { resolve({parseError: e.message}); } });
                        return orig(blob);
                    };
                    try { window.exportSystemJSON(id); } catch(e) { URL.createObjectURL = orig; resolve({error: e.message}); }
                    setTimeout(() => resolve({timeout: true}), 3000);
                });
            }""",
                sid,
            )
            ok = (
                isinstance(result, dict)
                and result.get("syntheticCase") == expect_synth
                and result.get("buildInfo", {}).get("buildId") == build_info["buildId"]
            )
            check(label, ok, json.dumps({"syntheticCase": result.get("syntheticCase"), "schema": result.get("schema")}))

        # Single-output DOCX builder (ZIP's /docs folder) -- functional + metadata + banner.
        docx_check = page.evaluate(
            """async (id) => {
            const s = st.systems.find(x=>x.id===id);
            const blob = await buildSingleOutputDocxBlob(s, s.generatedOutputs[0]);
            const z = await JSZip.loadAsync(blob);
            const doc = await z.file('word/document.xml').async('string');
            const core = await z.file('docProps/core.xml').async('string');
            return { size: blob.size, hasBanner: doc.includes('SYNTHETIC REGULATORY TEST CASE'), coreHasBuildId: core.includes(BUILD_INFO.buildId) || core.includes(BUILD_INFO.exportPackageVersion) };
        }""",
            synth_id,
        )
        check("buildSingleOutputDocxBlob functional (synthetic)", docx_check["size"] > 1000, "size=" + str(docx_check["size"]))
        check("Synthetic banner present in single-output DOCX", docx_check["hasBanner"], "")
        check("Single-output DOCX core.xml carries BUILD_INFO", docx_check["coreHasBuildId"], "")

        docx_check_real = page.evaluate(
            """async (id) => {
            const s = st.systems.find(x=>x.id===id);
            const blob = await buildSingleOutputDocxBlob(s, s.generatedOutputs[0]);
            const z = await JSZip.loadAsync(blob);
            const doc = await z.file('word/document.xml').async('string');
            return {hasBanner: doc.includes('SYNTHETIC REGULATORY TEST CASE')};
        }""",
            real_id,
        )
        check("Real case single-output DOCX has NO synthetic banner", docx_check_real["hasBanner"] is False, "")

        # Canonical multi-output pipeline (__eaceV32.buildDocx/buildPdf) -- reused by
        # the Export Centre, ZIP export, and exportSystemDOCX/PDF's live dispatch chain.
        canonical_check = page.evaluate(
            """async (id) => {
            const s = st.systems.find(x=>x.id===id);
            if(!window.__eaceV32) return {error: 'no __eaceV32'};
            const items = __eaceV32.outputs(s);
            const docxBlob = await __eaceV32.buildDocx(s, items, 'Complete Regulatory Documentation');
            const pdfBlob = await __eaceV32.buildPdf(s, items, 'Complete Regulatory Documentation');
            const z = await JSZip.loadAsync(docxBlob);
            const doc = await z.file('word/document.xml').async('string');
            const core = await z.file('docProps/core.xml').async('string');
            return { docxSize: docxBlob.size, pdfSize: pdfBlob.size, docxHasBanner: doc.includes('SYNTHETIC REGULATORY TEST CASE'), coreHasBuildId: core.includes(BUILD_INFO.exportPackageVersion) };
        }""",
            synth_id,
        )
        check(
            "Canonical buildDocx+buildPdf functional (synthetic)",
            canonical_check.get("docxSize", 0) > 1000 and canonical_check.get("pdfSize", 0) > 500,
            str({k: v for k, v in canonical_check.items() if k != "coreHasBuildId"}),
        )
        check("Canonical buildDocx carries synthetic banner", canonical_check.get("docxHasBanner") is True, "")
        check("Canonical buildDocx core.xml carries BUILD_INFO", canonical_check.get("coreHasBuildId") is True, "")

        canonical_check_real = page.evaluate(
            """async (id) => {
            const s = st.systems.find(x=>x.id===id);
            const items = __eaceV32.outputs(s);
            const docxBlob = await __eaceV32.buildDocx(s, items, 'Complete Regulatory Documentation');
            const z = await JSZip.loadAsync(docxBlob);
            const doc = await z.file('word/document.xml').async('string');
            return {hasBanner: doc.includes('SYNTHETIC REGULATORY TEST CASE')};
        }""",
            real_id,
        )
        check("Real case canonical DOCX has NO synthetic banner", canonical_check_real["hasBanner"] is False, "")

        # Real ZIP export (__eaceV42.exportZip) -- inspect the actual manifest.json produced.
        def zip_manifest(sid):
            return page.evaluate(
                """async (id) => {
                return new Promise((resolve) => {
                    const s = st.systems.find(x=>x.id===id);
                    const orig = URL.createObjectURL;
                    URL.createObjectURL = (blob) => {
                        blob.arrayBuffer().then(async buf => {
                            URL.createObjectURL = orig;
                            try {
                                const z = await JSZip.loadAsync(buf);
                                resolve(JSON.parse(await z.file('manifest.json').async('string')));
                            } catch(e) { resolve({error: e.message}); }
                        });
                        return orig(blob);
                    };
                    const items = __eaceV42.outputs(s, 'complete');
                    __eaceV42.exportZip(s, 'complete', items).catch(e => resolve({error: e.message}));
                    setTimeout(() => resolve({timeout: true}), 8000);
                });
            }""",
                sid,
            )

        zip_synth = zip_manifest(synth_id)
        check(
            "Real ZIP export manifest carries buildInfo+syntheticCase=true",
            isinstance(zip_synth, dict) and zip_synth.get("syntheticCase") is True and (zip_synth.get("buildInfo") or {}).get("buildId") == build_info["buildId"],
            json.dumps(zip_synth),
        )
        zip_real = zip_manifest(real_id)
        check("Real case ZIP manifest syntheticCase=false", isinstance(zip_real, dict) and zip_real.get("syntheticCase") is False, json.dumps(zip_real))

        # Workspace export round-trip (window.__eaceV44.exportHeaderJson) preserves per-system flags.
        roundtrip = page.evaluate(
            """async (ids) => {
            const blob = window.__eaceV44.exportHeaderJson();
            const text = await blob.text();
            const payload = JSON.parse(text);
            const restored = payload.systems.map(s=>Object.assign({},s));
            const rs = restored.find(s=>s.id===ids.synth), rr = restored.find(s=>s.id===ids.real);
            return { hasBuildInfo: !!payload.buildInfo, buildId: payload.buildInfo && payload.buildInfo.buildId,
                     restoredSynthFlag: rs ? rs.isSyntheticCase : 'MISSING', restoredRealFlag: rr ? rr.isSyntheticCase : 'MISSING' };
        }""",
            {"real": real_id, "synth": synth_id},
        )
        check(
            "Workspace export round-trip preserves flags + carries buildInfo",
            roundtrip["restoredSynthFlag"] is True and roundtrip["restoredRealFlag"] is False and roundtrip["hasBuildInfo"] and roundtrip["buildId"] == build_info["buildId"],
            json.dumps(roundtrip),
        )

        # Legacy import (no isSyntheticCase field) must load without being misclassified.
        legacy_check = page.evaluate("""() => {
            const legacyPayload = { schema: 'EACE_CASE_EXPORT_V42', system: { id: 'sys_legacy_import', name: 'Legacy Imported System', status:'Draft', pillar:'P1', data:{} }, generatedOutputs: [] };
            const inc = [Object.assign({}, legacyPayload.system, {generatedOutputs: legacyPayload.system.generatedOutputs || []})];
            const restored = inc[0];
            return {loaded: !!restored, syntheticFlag: restored.isSyntheticCase, hasName: restored.name === 'Legacy Imported System'};
        }""")
        check(
            "Legacy JSON (no isSyntheticCase field) loads, NOT auto-classified synthetic",
            legacy_check["loaded"] and legacy_check["syntheticFlag"] is not True and legacy_check["hasName"],
            json.dumps(legacy_check),
        )

        print()
        print("page errors during full run:", errors)
        total = len(RESULTS)
        passed = sum(1 for _, ok, _ in RESULTS if ok)
        print(f"\n{passed}/{total} checks passed")
        browser.close()

        sys.exit(0 if passed == total and not errors else 1)


if __name__ == "__main__":
    main()
