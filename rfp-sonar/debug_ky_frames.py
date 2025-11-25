#!/usr/bin/env python3
"""
Debug script to identify iframe structure and locate Published Solicitations button
"""
import os
from playwright.sync_api import sync_playwright

# Get credentials from environment
KY_VSS_USERNAME = os.environ.get('KY_VSS_USERNAME', 'rfpsonar')
KY_VSS_PASSWORD = os.environ.get('KY_VSS_PASSWORD', 'fYrqyb-8nyrfo')
PORTAL_URL = 'https://vss.ky.gov/'

def debug_frames():
    print("=" * 80)
    print("KENTUCKY VSS FRAME STRUCTURE DEBUG")
    print("=" * 80)

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # Start tracing for detailed analysis
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()

        try:
            # Navigate to portal and login
            print(f"\n[1] Navigating to {PORTAL_URL}...")
            page.goto(PORTAL_URL)
            page.wait_for_timeout(2000)

            print("[2] Logging in...")
            page.get_by_role("textbox", name="User ID").fill(KY_VSS_USERNAME)
            page.get_by_role("textbox", name="Password").fill(KY_VSS_PASSWORD)
            page.get_by_role("button", name="Sign In").click()

            print("[3] Waiting for dashboard to load...")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(15000)  # Extra wait for Angular

            print(f"\n[4] Current URL: {page.url}")
            print(f"[5] Page Title: {page.title()}")

            # ============================================================
            # FRAME ANALYSIS
            # ============================================================
            print("\n" + "=" * 80)
            print("FRAME STRUCTURE ANALYSIS")
            print("=" * 80)

            frames = page.frames
            print(f"\nTotal frames found: {len(frames)}")

            for idx, frame in enumerate(frames):
                print(f"\n--- Frame {idx} ---")
                print(f"  Name: {frame.name}")
                print(f"  URL: {frame.url}")

                # Try to find Published Solicitations in this frame
                try:
                    ps_count = frame.locator("text=Published Solicitations").count()
                    print(f"  'Published Solicitations' text occurrences: {ps_count}")

                    if ps_count > 0:
                        print(f"  *** FOUND IN THIS FRAME! ***")

                        # Try to find buttons in this frame
                        button_count = frame.locator("button").count()
                        print(f"  Total buttons in frame: {button_count}")

                        # Try to find the specific button
                        ps_button_count = frame.locator("button:has-text('Published Solicitations')").count()
                        print(f"  Buttons with 'Published Solicitations' text: {ps_button_count}")

                        if ps_button_count > 0:
                            print(f"  *** BUTTON IS CLICKABLE IN THIS FRAME! ***")

                            # Get button details
                            button = frame.locator("button:has-text('Published Solicitations')").first
                            try:
                                aria_label = button.get_attribute("aria-label")
                                css_class = button.get_attribute("class")
                                data_qan = button.get_attribute("data-qan")
                                print(f"  Button aria-label: {aria_label}")
                                print(f"  Button class: {css_class}")
                                print(f"  Button data-qan: {data_qan}")
                            except Exception as e:
                                print(f"  Could not get button attributes: {e}")

                except Exception as e:
                    print(f"  Error searching frame: {e}")

            # ============================================================
            # IFRAME DETECTION
            # ============================================================
            print("\n" + "=" * 80)
            print("IFRAME ELEMENT DETECTION")
            print("=" * 80)

            iframe_elements = page.locator("iframe").count()
            print(f"\nTotal <iframe> elements: {iframe_elements}")

            if iframe_elements > 0:
                for i in range(iframe_elements):
                    iframe = page.locator("iframe").nth(i)
                    name = iframe.get_attribute("name") or "(unnamed)"
                    src = iframe.get_attribute("src") or "(no src)"
                    id_attr = iframe.get_attribute("id") or "(no id)"
                    print(f"\niframe {i}:")
                    print(f"  name: {name}")
                    print(f"  id: {id_attr}")
                    print(f"  src: {src}")

            # ============================================================
            # DOM INSPECTION
            # ============================================================
            print("\n" + "=" * 80)
            print("DOM CONTENT SAMPLE")
            print("=" * 80)

            html = page.content()
            print(f"\nTotal HTML length: {len(html)} characters")
            print("\nFirst 5000 characters:")
            print(html[:5000])

            # ============================================================
            # BUTTON SEARCH IN MAIN PAGE
            # ============================================================
            print("\n" + "=" * 80)
            print("MAIN PAGE BUTTON ANALYSIS")
            print("=" * 80)

            all_buttons = page.locator("button").count()
            print(f"\nTotal buttons in main page: {all_buttons}")

            if all_buttons > 0:
                print("\nFirst 10 buttons:")
                for i in range(min(10, all_buttons)):
                    try:
                        button = page.locator("button").nth(i)
                        text = button.inner_text()
                        aria = button.get_attribute("aria-label") or "(no aria-label)"
                        print(f"  {i}: text='{text[:50]}' aria-label='{aria[:50]}'")
                    except:
                        pass

            # ============================================================
            # ATTEMPT CLICK IN CORRECT FRAME
            # ============================================================
            print("\n" + "=" * 80)
            print("ATTEMPTING TO CLICK IN IDENTIFIED FRAME")
            print("=" * 80)

            clicked = False
            for idx, frame in enumerate(frames):
                try:
                    ps_button_count = frame.locator("button:has-text('Published Solicitations')").count()
                    if ps_button_count > 0:
                        print(f"\nAttempting click in Frame {idx} ({frame.name})...")
                        button = frame.locator("button:has-text('Published Solicitations')").first
                        button.click(timeout=10000)
                        print(f"✓ Successfully clicked button in Frame {idx}!")
                        clicked = True

                        # Wait for navigation
                        page.wait_for_timeout(5000)
                        print(f"New URL after click: {page.url}")
                        break
                except Exception as e:
                    print(f"  Click failed in Frame {idx}: {e}")

            if not clicked:
                print("\n❌ Could not click button in any frame")

            # Take screenshot
            screenshot_path = "/tmp/ky_debug_frames.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n📸 Screenshot saved: {screenshot_path}")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Save trace
            context.tracing.stop(path="/tmp/trace.zip")
            print(f"\n📦 Trace saved: /tmp/trace.zip")
            print("   Upload to https://trace.playwright.dev/ for detailed analysis")

            browser.close()

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    debug_frames()
