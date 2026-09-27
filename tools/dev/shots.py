import sys
from playwright.sync_api import sync_playwright

BASE = "https://localhost:5443"
out = sys.argv[1]
only = set(sys.argv[2:])


def session(p, user, height=900):
    ctx = p.chromium.launch().new_context(viewport={"width": 1440, "height": height}, ignore_https_errors=True)
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(BASE)
    page.fill("#username", user); page.fill("#password", "dev-only-password"); page.click("#kc-login")
    page.wait_for_selector(".sidebar", timeout=20000); page.wait_for_timeout(1200)
    return page, errors


def shot(page, name, path=None, wait=1800):
    if only and name not in only:
        return
    if path:
        page.goto(BASE + path)
    page.wait_for_timeout(wait)
    page.screenshot(path=f"{out}/{name}.png")


with sync_playwright() as p:
    page, errors = session(p, "rita.radiologist")
    shot(page, "overview", "/overview")
    shot(page, "worklist", "/worklist")
    shot(page, "worklist-neurology", "/worklist/neurology")
    if not only or "study" in only:
        page.goto(BASE + "/worklist"); page.wait_for_timeout(1500)
        link = page.locator("a.button").first
        (link if link.count() else page.locator("button.small-button").first).click()
        shot(page, "study", wait=3500)
    tall, _ = session(p, "rita.radiologist", height=2400)
    shot(tall, "upload", "/upload")
    shot(tall, "models", "/models")
    print("rita errors:", errors)
    page, errors = session(p, "ada.admin", height=2400)
    shot(page, "models-admin", "/models")
    print("ada errors:", errors)
