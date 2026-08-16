"""
P1 regression (Golden Artefact Acceptance remediation): assessArtefactCompleteness
must not depend primarily on English lexical regexes. This test re-checks the
four German artefacts from the Golden Artefact Acceptance run (RMS, QMS,
FRIA, Contracts) plus one new Croatian artefact, and confirms the SAME
structurally-complete content scores materially equivalently regardless of
documentation language -- the specific failure mode confirmed in that run
was German "Eskalationspfad" not matching /escalat/i, German "§1" clauses
not matching /\bclause\b|\barticle\s*\d/i, German "Verarbeitung" not
matching /\bprocessing\b/i, etc.

Part A: parallel EN/DE/HR fixtures of the SAME structurally-complete
SOP_PROCEDURE-type content (equivalent meaning, different language) must
score the same STRUCTURALLY_COMPLETE status and a materially equivalent
coverage (within a small tolerance -- not identical, since the lexical
fallback dictionaries are not perfectly parallel across languages, but not
an order-of-magnitude gap either).

Part B: re-runs assessArtefactCompleteness against the actual German RMS/
QMS/FRIA/Contracts texts used in the Golden Artefact Acceptance run and
confirms the specific dimensions that previously false-negatived
(PURPOSE_SCOPE, ESCALATION, OPERATIVE_CLAUSES, ROLES_RESPONSIBILITIES) are
now correctly detected as present, given the content genuinely covers them
in German.

Part C: one new Croatian RMS-equivalent fixture, confirming Croatian is
correctly picked up by the lexical fallback layer too (not just German).

Usage:
    python3 -m http.server 8899 &
    python3 tests/verify_step11_language_neutral_completeness.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"
SCRATCH = "/tmp/claude-0/-home-user-eace-ai/278e4d47-1dd0-5c6c-8b38-3a036aa152be/scratchpad"

# --- Part A: parallel EN/DE/HR fixtures, same structural content ---------
EN_SOP = (
    "Risk Management System Plan\n\n"
    "Purpose and scope: this plan covers the full lifecycle of the system.\n\n"
    "Roles: the Compliance Officer is the owner and is responsible for this document.\n\n"
    "Step 1. Identify hazards using the taxonomy below.\n"
    "Step 2. Assess severity and likelihood on the defined scale.\n"
    "Step 3. Escalate to the Risk Owner whenever a trigger condition is met.\n\n"
    "Evidence and records: every finding is logged in the Risk Register with a unique ID.\n\n"
    "Review and approval: this plan is reviewed quarterly and approved by the Quality Manager."
)
DE_SOP = (
    "Risikomanagementsystem-Plan\n\n"
    "Zweck und Anwendungsbereich: dieser Plan deckt den gesamten Lebenszyklus des Systems ab.\n\n"
    "Rollen: der Compliance-Beauftragte ist Eigentümer und verantwortlich für dieses Dokument.\n\n"
    "Schritt 1. Gefahren anhand der untenstehenden Taxonomie identifizieren.\n"
    "Schritt 2. Schweregrad und Wahrscheinlichkeit auf der definierten Skala bewerten.\n"
    "Schritt 3. Bei Erreichen eines Auslösers an den Risikoeigentümer eskalieren.\n\n"
    "Nachweise und Aufzeichnungen: jeder Befund wird mit eindeutiger ID im Risikoregister erfasst.\n\n"
    "Überprüfung und Genehmigung: dieser Plan wird vierteljährlich überprüft und vom Qualitätsmanager genehmigt."
)
HR_SOP = (
    "Plan sustava upravljanja rizicima\n\n"
    "Svrha i opseg: ovaj plan obuhvaća cijeli životni ciklus sustava.\n\n"
    "Uloge: službenik za usklađenost je vlasnik i odgovoran je za ovaj dokument.\n\n"
    "Korak 1. Identificirati opasnosti prema donjoj taksonomiji.\n"
    "Korak 2. Procijeniti ozbiljnost i vjerojatnost na definiranoj skali.\n"
    "Korak 3. Eskalirati vlasniku rizika kada je ispunjen okidački uvjet.\n\n"
    "Dokazi i evidencija: svaki nalaz bilježi se u registru rizika s jedinstvenim ID-om.\n\n"
    "Pregled i odobrenje: ovaj plan se pregledava tromjesečno i odobrava ga voditelj kvalitete."
)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE_URL, wait_until="networkidle")
    if "ENTER WORKSPACE" in page.inner_text("body"):
        page.fill('input[placeholder="Name or identifier"]', "LangNeutralCheck", timeout=3000)
        page.click("text=ENTER WORKSPACE", timeout=3000)
        page.wait_for_timeout(1000)

    fails = []
    out03 = page.evaluate("() => OUTPUTS.P2A.find(o => o.code === 'O03')")

    # --- Part A ---
    results = {}
    for label, text in [("EN", EN_SOP), ("DE", DE_SOP), ("HR", HR_SOP)]:
        r = page.evaluate("([p, o, t]) => assessArtefactCompleteness(p, o, t)", ["P2A", out03, text])
        results[label] = r
        print(f"{label}: status={r['status']} coverage={r['coverage']} found={r['dimensionsFound']} missing={r['dimensionsMissing']}")

    statuses = {results[l]["status"] for l in ("EN", "DE", "HR")}
    print(f"\nStatus set across EN/DE/HR: {statuses}")
    if len(statuses) > 1:
        fails.append(f"EN/DE/HR parallel fixtures did not receive the same status: {[(l, results[l]['status']) for l in ('EN','DE','HR')]}")

    coverages = [results[l]["coverage"] for l in ("EN", "DE", "HR")]
    spread = max(coverages) - min(coverages)
    print(f"Coverage spread across EN/DE/HR: {spread:.2f} (values: {coverages})")
    if spread > 0.20:
        fails.append(f"EN/DE/HR coverage spread too large (language-driven false negative): {coverages}")

    # --- Part B: re-check the actual German Golden Artefact Acceptance fixtures ---
    GOLDEN_TARGETS = [
        ("RMS", "P2A", "O03", f"{SCRATCH}/synthetic_rms.md", ["PURPOSE_SCOPE", "ESCALATION"]),
        ("QMS", "P2A", "O11", f"{SCRATCH}/synthetic_qms.md", ["PURPOSE_SCOPE"]),
        ("FRIA", "P2B", "O06", f"{SCRATCH}/synthetic_fria.md", ["PURPOSE_SCOPE"]),
        ("Contracts", "P2A", "O25", f"{SCRATCH}/synthetic_contracts.md", ["OPERATIVE_CLAUSES", "ROLES_RESPONSIBILITIES"]),
    ]
    for label, pillar, code, path, expect_found_dims in GOLDEN_TARGETS:
        p = Path(path)
        if not p.exists():
            print(f"SKIP {label}: fixture {path} not found (Golden Artefact Acceptance scratch files not present in this environment)")
            continue
        text = p.read_text(encoding="utf-8")
        out = page.evaluate(f"() => OUTPUTS['{pillar}'].find(o => o.code === '{code}')")
        r = page.evaluate("([p, o, t]) => assessArtefactCompleteness(p, o, t)", [pillar, out, text])
        print(f"\n{label} ({pillar}/{code}): status={r['status']} coverage={r['coverage']}")
        print(f"  found={r['dimensionsFound']}")
        print(f"  missing={r['dimensionsMissing']}")
        for dim in expect_found_dims:
            hit = any(dim in f for f in r["dimensionsFound"])
            ok = "OK" if hit else "FAIL"
            print(f"  {ok}  {dim} detected: {hit}")
            if not hit:
                fails.append(f"{label}: expected canonical dimension {dim!r} to be detected in the real German fixture, but it was in dimensionsMissing: {r['dimensionsMissing']}")

    # --- Part C: standalone Croatian RMS check already covered by Part A's HR_SOP,
    # but confirm explicitly that Croatian PROCEDURE/ESCALATION/EVIDENCE/APPROVAL
    # dimensions are individually detected (not just an aggregate coverage number).
    hr_result = results["HR"]
    for dim in ["ESCALATION", "PROCEDURE", "EVIDENCE", "APPROVAL", "PURPOSE_SCOPE", "ROLES_RESPONSIBILITIES"]:
        hit = any(dim in f for f in hr_result["dimensionsFound"])
        print(f"{'OK' if hit else 'FAIL'}  Croatian fixture: {dim} detected: {hit}")
        if not hit:
            fails.append(f"Croatian fixture: expected {dim} detected, got dimensionsFound={hr_result['dimensionsFound']}")

    print(f"\nFAILURES: {len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    print("page errors:", errors)
    browser.close()
    sys.exit(0 if (not fails and not errors) else 1)
