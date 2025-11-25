#!/usr/bin/env python3
"""
Local debug script - runs Kentucky scraper with VISIBLE browser
Run this to watch exactly what's happening step-by-step
"""
import os
from playwright.sync_api import sync_playwright

# Credentials
VSS_USER = os.getenv("KY_VSS_USERNAME", "rfpsonar")
VSS_PASS = os.getenv("KY_VSS_PASSWORD", "fYrqyb-8nyrfo")
PORTAL_URL = "https://vss.ky.gov/"

print("=" * 80)
print("KENTUCKY VSS - LOCAL DEBUG WITH VISIBLE BROWSER")
print("=" * 80)
print("\nThis will open a browser window so you can watch the scraper in action.")
print("The browser will stay open at each step so you can inspect the page.\n")

with sync_playwright() as p:
    # Launch browser in HEADED mode (visible)
    print("[1] Launching visible browser...")
    browser = p.chromium.launch(
        headless=False,  # VISIBLE BROWSER!
        slow_mo=1000     # Slow down actions by 1 second so you can see them
    )

    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()

    try:
        # STEP 1: Navigate to login
        print(f"\n[2] Navigating to {PORTAL_URL}...")
        page.goto(PORTAL_URL)
        page.wait_for_timeout(2000)

        # STEP 2: Login
        print(f"\n[3] Logging in as {VSS_USER}...")
        page.get_by_role("textbox", name="User ID").fill(VSS_USER)
        page.get_by_role("textbox", name="Password").fill(VSS_PASS)
        page.get_by_role("button", name="Sign In").click()

        # Wait for dashboard
        page.wait_for_load_state("networkidle")
        print(f"\n[4] Current URL: {page.url}")
        print(f"[5] Page Title: {page.title()}")

        # STEP 3: Wait for dashboard to render
        print("\n[6] Waiting for dashboard tiles to render (15 seconds)...")
        page.wait_for_timeout(15000)

        # STEP 4: Click Published Solicitations
        print("\n[7] Looking for 'Published Solicitations' button...")
        pub_sol_button = page.locator("button[aria-label='Published Solicitations']").first
        pub_sol_button.wait_for(state="attached", timeout=10000)

        print("[8] Clicking 'Published Solicitations' button...")
        pub_sol_button.click(force=True)

        # STEP 5: Handle disclaimer modal
        print("\n[9] Checking for disclaimer modal...")
        try:
            agree_button = page.get_by_role("button", name="I Agree")
            if agree_button.is_visible(timeout=5000):
                print("     ✓ Disclaimer modal found - clicking 'I Agree'...")
                agree_button.click()
                page.wait_for_timeout(2000)
                print("     ✓ Clicked 'I Agree'")
            else:
                print("     No disclaimer modal visible")
        except Exception as e:
            print(f"     No disclaimer modal: {e}")

        # STEP 6: Wait for navigation
        print("\n[10] Waiting for Published Solicitations page to load...")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        print(f"\n[11] After disclaimer - URL: {page.url}")
        print(f"[12] After disclaimer - Title: {page.title()}")

        # STEP 6: Check for table
        print("\n[12] Looking for table on the page...")
        print(f"     Waiting for table selector: table[summary='Search Results']")

        try:
            table = page.locator("table[summary='Search Results']")
            table.wait_for(state="visible", timeout=10000)
            print("     ✓ Table found!")

            rows = table.locator("tbody > tr").all()
            print(f"     Found {len(rows)} rows in table")

        except Exception as e:
            print(f"     ✗ Table not found: {e}")
            print("\n     Let's check what tables ARE on the page:")
            all_tables = page.locator("table").all()
            print(f"     Total tables found: {len(all_tables)}")

            for idx, tbl in enumerate(all_tables):
                summary = tbl.get_attribute("summary") or "(no summary)"
                print(f"       Table {idx}: summary='{summary}'")

        # STEP 7: Look for Status dropdown
        print("\n[13] Looking for Status dropdown...")
        try:
            status_dropdown = page.locator("select[name*='Status']").first
            if status_dropdown.is_visible():
                print("     ✓ Status dropdown found and visible")
            else:
                print("     ✗ Status dropdown exists but not visible")
        except Exception as e:
            print(f"     ✗ Status dropdown not found: {e}")

        # STEP 8: Take screenshot
        screenshot_path = "/tmp/ky_local_debug.png"
        page.screenshot(path=screenshot_path)
        print(f"\n[14] Screenshot saved: {screenshot_path}")

        # PAUSE - Keep browser open so you can inspect
        print("\n" + "=" * 80)
        print("BROWSER WILL STAY OPEN - Press Enter to continue and close browser...")
        print("=" * 80)
        input()

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

        print("\nBrowser will stay open so you can inspect the error state.")
        print("Press Enter to close...")
        input()

    finally:
        browser.close()
        print("\n✓ Browser closed")
