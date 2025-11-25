"""
Kentucky VSS (Vendor Self Service) Portal Scraper
CGI Advantage 4.0 Platform
Requires authentication
"""
from .base_scraper import BaseScraper
from playwright.sync_api import sync_playwright
import os
import re
import requests
from datetime import datetime


class KentuckyScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.jurisdiction_code = 'KY'  # Matches Salesforce Account Billing_State_Code__c
        self.portal_url = 'https://vss.ky.gov/'

        # Load Credentials from environment
        self.vss_user = os.environ.get('KY_VSS_USERNAME')
        self.vss_pass = os.environ.get('KY_VSS_PASSWORD')

        # Kentucky Account ID (Commonwealth of Kentucky)
        self.account_id = '001V400000dOSjKIAW'

    def get_account_id(self):
        """Return Account ID (required by base class)"""
        return self.account_id

    def _query_account_id(self):
        """Query Salesforce for Kentucky Account ID"""
        headers = {
            'Authorization': f'Bearer {self.sf_api_key}',
            'Content-Type': 'application/json'
        }
        query = f"SELECT Id FROM Account WHERE BillingState = '{self.jurisdiction_code}'"
        url = f"{self.sf_instance_url}/services/data/v65.0/query/?q={query}"

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            records = response.json().get('records', [])
            if records:
                return records[0]['Id']
        raise ValueError(f"Could not find Account for jurisdiction: {self.jurisdiction_code}")

    def parse_date(self, date_str):
        """
        Parses VSS date format: "10/14/2025 03:30 PM EDT"
        Returns YYYY-MM-DD string
        """
        try:
            if not date_str:
                return None
            # Remove timezone/extra text if present (e.g. " EDT")
            clean_date = date_str.split(' ')[0]
            return datetime.strptime(clean_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        except Exception as e:
            print(f"  Date parse error for '{date_str}': {e}")
            return None

    def scrape(self):
        print(f"Starting Kentucky VSS Scrape for Account: {self.account_id}")

        if not self.vss_user or not self.vss_pass:
            raise ValueError("Missing KY_VSS_USERNAME or KY_VSS_PASSWORD environment variables.")

        try:
            # 1. Deduplication: Get existing Solicitation Numbers from Salesforce
            existing_numbers = self.get_existing_solicitation_numbers(self.account_id)
            print(f"Found {len(existing_numbers)} existing solicitations in Salesforce.")

            with sync_playwright() as p:
                # Launch Headless Chrome
                browser = p.chromium.launch(headless=True)
                # Set User Agent to avoid basic bot detection
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                page = context.new_page()

                # --- STEP 1: LOGIN ---
                print("Navigating to VSS Login...")
                page.goto(self.portal_url)

                # Fill Login Form (Using role+name for uniqueness)
                print(f"Logging in as {self.vss_user}...")
                page.get_by_role("textbox", name="User ID").fill(self.vss_user)
                page.get_by_role("textbox", name="Password").fill(self.vss_pass)
                page.get_by_role("button", name="Sign In").click()

                # Wait for Dashboard to load
                page.wait_for_load_state("networkidle")

                # --- STEP 2: NAVIGATE TO PUBLISHED SOLICITATIONS ---
                print("Navigating to Published Solicitations...")

                # The dashboard is a JavaScript SPA (Angular) that renders tiles dynamically
                # Wait for the button elements to be rendered
                print("Waiting for dashboard tiles to render (Angular SPA)...")
                page.wait_for_timeout(15000)  # Give Angular extra time to bootstrap and render

                print("Looking for Published Solicitations button...")
                # The Published Solicitations tile is a button with aria-label
                # Wait for it to be actionable (visible, enabled, and stable)
                try:
                    pub_sol_button = page.locator("button[aria-label='Published Solicitations']").first
                    # Wait for button to be actionable (not just visible)
                    pub_sol_button.wait_for(state="attached", timeout=10000)
                    # Force click to bypass actionability checks (Angular may be intercepting clicks)
                    pub_sol_button.click(force=True)
                    print("✓ Clicked Published Solicitations button")
                except Exception as e:
                    print(f"Button click failed: {e}")
                    raise

                # Handle Disclaimer modal if it appears
                print("Checking for disclaimer modal...")
                try:
                    agree_button = page.get_by_role("button", name="I Agree")
                    if agree_button.is_visible(timeout=5000):
                        print("Disclaimer modal appeared - clicking 'I Agree'...")
                        agree_button.click()
                        page.wait_for_timeout(2000)
                        print("✓ Clicked 'I Agree' button")

                        # After dismissing disclaimer, need to click Published Solicitations AGAIN
                        print("Clicking 'Published Solicitations' again after disclaimer...")
                        pub_sol_button_retry = page.locator("button[aria-label='Published Solicitations']").first
                        pub_sol_button_retry.click(force=True)
                        print("✓ Clicked 'Published Solicitations' second time")
                except Exception:
                    print("No disclaimer modal (or already dismissed)")

                # Wait for navigation to Published Solicitations page
                print("Waiting for Published Solicitations page to load...")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(5000)  # Give Angular time to render the search form

                # --- STEP 3: SEARCH & FILTER ---
                print("Filtering for OPEN solicitations...")

                # Wait for the Search Grid/Form to be visible
                page.wait_for_selector("table", state="visible", timeout=30000)

                # Set Status filter to "Open"
                try:
                    status_dropdown = page.locator("select").filter(has_text="Open").first
                    status_dropdown.wait_for(state="visible", timeout=5000)
                    status_dropdown.select_option(label="Open")
                    print("✓ Selected 'Open' status")

                    # Click the specific Search button (use aria-label to avoid ambiguity)
                    search_button = page.get_by_label("Search", exact=True)
                    search_button.click()
                    print("✓ Clicked Search button")

                    # Wait for table refresh
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"Warning: Could not filter by status: {e}")

                # Set pagination to 100 records per page
                try:
                    page.get_by_text("100", exact=True).click()
                    print("✓ Set to 100 records per page")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"Warning: Could not set pagination: {e}")

                # Sort by Closing Date (ascending - earliest deadlines first)
                try:
                    closing_date_header = page.locator("th").filter(has_text="Closing Date and Time/Status").first
                    closing_date_header.click()
                    print("✓ Sorted by closing date (earliest first)")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"Warning: Could not sort by closing date: {e}")

                # --- STEP 4: EXTRACT DATA ---
                # Select all rows in the results table
                # The results table contains columns: Description, Department/Buyer, Solicitation Number/Type/Category, Closing Date
                # It's the second table on the page (first is the search form filters)
                rows = page.locator("table").nth(1).locator("tbody > tr").all()
                print(f"Found {len(rows)} rows in search results.")

                new_opps_count = 0

                for row in rows:
                    try:
                        cells = row.locator("td").all()
                        # Ensure row has enough columns (skipping headers/empty rows)
                        if len(cells) < 6:
                            continue

                        # Column Mapping (6 cells per row):
                        # Cell 0: Expand icon (empty)
                        # Cell 1: Description / Title
                        # Cell 2: Department / Buyer
                        # Cell 3: Solicitation Number / Type / Category (multiline)
                        # Cell 4: Closing Date / Status (multiline)
                        # Cell 5: "Respond" button

                        description_raw = cells[1].inner_text().strip()
                        solicitation_raw = cells[3].inner_text().strip()
                        date_raw = cells[4].inner_text().strip()

                        # Clean Solicitation ID (first line only)
                        solicitation_number = solicitation_raw.split('\n')[0].strip()

                        # Clean date (first line only - contains the actual date)
                        date_line = date_raw.split('\n')[0].strip()

                        # Deduplication: Skip if exists
                        if solicitation_number in existing_numbers:
                            # print(f"Skipping existing: {solicitation_number}")
                            continue

                        # Get Link (Essential for future phase: Attachments)
                        link_element = row.locator("a").first
                        if link_element.count() > 0:
                            link_href = link_element.get_attribute("href")
                            full_link = f"https://vss.ky.gov{link_href}" if link_href and link_href.startswith("/") else link_href
                        else:
                            full_link = self.portal_url

                        # Parse Date
                        close_date = self.parse_date(date_line)
                        if not close_date:
                            close_date = datetime.now().strftime('%Y-%m-%d')  # Fallback to today if parsing fails

                        # Construct Salesforce Opportunity Data
                        opp_data = {
                            'Name': description_raw[:120],  # SF Limit 120 chars
                            'AccountId': self.account_id,
                            'Solicitation_Number__c': solicitation_number,
                            'CloseDate': close_date,
                            'StageName': 'Prospecting',
                            'Description': (
                                f"Full Title: {description_raw}\n"
                                f"Solicitation ID: {solicitation_raw}\n"
                                f"Link: {full_link}\n"
                                f"Extracted Date: {date_raw}"
                            )
                        }

                        # Create in Salesforce
                        self.create_salesforce_opportunity(opp_data)
                        new_opps_count += 1
                        print(f"✓ Created: {solicitation_number}")

                    except Exception as row_error:
                        print(f"Error parsing row: {str(row_error)}")
                        continue

                browser.close()

            # 5. Success
            self.update_account_scrape_status(self.account_id, 'Success')
            print(f"Scrape Complete. Created {new_opps_count} new opportunities.")

        except Exception as e:
            # 6. Failure
            print(f"CRITICAL FAILURE: {str(e)}")
            self.update_account_scrape_status(self.account_id, 'Failed', str(e))
            raise
