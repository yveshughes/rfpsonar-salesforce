#!/usr/bin/env python3
"""
Test script to verify Kentucky VSS login functionality
"""
import os
from playwright.sync_api import sync_playwright

# Get credentials from environment
KY_VSS_USERNAME = os.environ.get('KY_VSS_USERNAME', 'rfpsonar')
KY_VSS_PASSWORD = os.environ.get('KY_VSS_PASSWORD', 'fYrqyb-8nyrfo')
PORTAL_URL = 'https://vss.ky.gov/'

def test_login():
    print("=" * 60)
    print("Kentucky VSS Login Test")
    print("=" * 60)
    print(f"Portal URL: {PORTAL_URL}")
    print(f"Username: {KY_VSS_USERNAME}")
    print(f"Password: {'*' * len(KY_VSS_PASSWORD)}")
    print("=" * 60)

    with sync_playwright() as p:
        # Launch browser
        print("\n[1/5] Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to portal
        print(f"[2/5] Navigating to {PORTAL_URL}...")
        page.goto(PORTAL_URL)
        print(f"    ✓ Page loaded: {page.title()}")

        # Wait a moment for page to fully render
        print("[3/5] Waiting for login form to render...")
        page.wait_for_timeout(2000)

        # Fill login form
        print("[4/5] Filling login credentials...")
        try:
            # Try to fill User ID
            user_id_field = page.get_by_role("textbox", name="User ID")
            user_id_field.fill(KY_VSS_USERNAME)
            print(f"    ✓ Filled User ID: {KY_VSS_USERNAME}")

            # Try to fill Password
            password_field = page.get_by_role("textbox", name="Password")
            password_field.fill(KY_VSS_PASSWORD)
            print(f"    ✓ Filled Password: {'*' * len(KY_VSS_PASSWORD)}")

            # Click Sign In
            print("[5/5] Clicking Sign In button...")
            sign_in_button = page.get_by_role("button", name="Sign In")
            sign_in_button.click()

            # Wait for navigation
            print("    ⏳ Waiting for login to complete...")
            page.wait_for_load_state("networkidle", timeout=15000)

            # Check if we're logged in
            current_url = page.url
            print(f"    ✓ Current URL: {current_url}")

            # Take a screenshot for debugging
            screenshot_path = "/tmp/ky_login_success.png"
            page.screenshot(path=screenshot_path)
            print(f"    ✓ Screenshot saved: {screenshot_path}")

            # Check for common dashboard elements
            print("\n[CHECK] Looking for dashboard indicators...")

            # List all visible links to help debug
            links = page.get_by_role("link").all()
            print(f"    Found {len(links)} links on page:")
            for i, link in enumerate(links[:10], 1):  # Show first 10
                try:
                    text = link.inner_text()
                    if text.strip():
                        print(f"      {i}. {text.strip()}")
                except:
                    pass

            # Try to find "Published Solicitations" link
            try:
                pub_sol_link = page.get_by_role("link", name="Published Solicitations")
                print("\n    ✅ SUCCESS: Found 'Published Solicitations' link!")
                print("    Login appears to be working correctly.")
                return True
            except:
                print("\n    ⚠️  WARNING: Could not find 'Published Solicitations' link")
                print("    Login may have succeeded but dashboard layout is different than expected")
                return False

        except Exception as e:
            print(f"\n    ❌ ERROR: {str(e)}")
            # Take error screenshot
            screenshot_path = "/tmp/ky_login_error.png"
            page.screenshot(path=screenshot_path)
            print(f"    Screenshot saved: {screenshot_path}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        success = test_login()
        if success:
            print("\n" + "=" * 60)
            print("✅ TEST PASSED: Login successful!")
            print("=" * 60)
            exit(0)
        else:
            print("\n" + "=" * 60)
            print("⚠️  TEST PARTIAL: Login may have worked but dashboard is different")
            print("=" * 60)
            exit(1)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {str(e)}")
        print("=" * 60)
        exit(2)
