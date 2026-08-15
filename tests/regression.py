"""
Runs the app's built-in classification-integrity self-test
(runP1ClassificationIntegrityTests(), defined in index.html) headlessly.

Usage:
    python3 -m http.server 8899 &   # from the repo root
    python3 tests/regression.py [base_url]

Expects 10/10 to pass and an empty page-errors list. Treat either
failure as a real regression, not noise — this is the fastest signal
available for changes touching classification, routing, or shared state.
"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/index.html"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(0.5)

        if "ENTER WORKSPACE" in page.inner_text("body"):
            page.fill('input[placeholder="Name or identifier"]', "Regression", timeout=3000)
            page.click("text=ENTER WORKSPACE", timeout=3000)
            time.sleep(1)

        report = page.evaluate("() => runP1ClassificationIntegrityTests()")
        passed, total = report["passed"], report["total"]
        print(f"SELF-TESTS: {passed} / {total}")
        for r in report["results"]:
            if not r["pass"]:
                print("  FAIL:", r["name"], "—", r["detail"])
        print("page errors:", errors)
        browser.close()

        ok = passed == total and not errors
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
