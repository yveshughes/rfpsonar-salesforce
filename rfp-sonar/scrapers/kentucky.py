"""
Kentucky VSS (Vendor Self Service) Portal Scraper
CGI Advantage 4.0 Platform
Requires authentication
"""
from .base_scraper import BaseScraper
from playwright.sync_api import sync_playwright
import os
import re
from datetime import datetime


class KentuckyScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.jurisdiction_code = 'KY'  # Matches Salesforce Account Billing_State_Code__c
        self.portal_url = 'https://vss.ky.gov/'

        # Load Credentials from environment
        self.vss_user = os.environ.get('KY_VSS_USERNAME')
        self.vss_pass = os.environ.get('KY_VSS_PASSWORD')

        # Get Account ID from Salesforce
        self.account_id = self.get_account_id()

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

                # Fill Login Form (Using labels for robustness)
                print(f"Logging in as {self.vss_user}...")
                page.get_by_label("User ID").fill(self.vss_user)
                page.get_by_label("Password").fill(self.vss_pass)
                page.get_by_role("button", name="Sign In").click()

                # Wait for Dashboard to load
                page.wait_for_load_state("networkidle")

                # --- STEP 2: NAVIGATE TO PUBLISHED SOLICITATIONS ---
                print("Navigating to Published Solicitations...")
                # Click the large tab/icon shown in video
                page.get_by_role("link", name="Published Solicitations").click()

                # --- STEP 3: SEARCH & FILTER ---
                print("Filtering for OPEN solicitations...")

                # Wait for the Search Grid/Form to be visible
                page.wait_for_selector("table", state="visible", timeout=30000)

                # Interact with Status Dropdown
                # The video shows a dropdown labeled "Status". We select "Open".
                status_dropdown = page.locator("select[name*='Status']")

                if status_dropdown.is_visible():
                    status_dropdown.select_option(label="Open")

                    # Click Search
                    page.get_by_role("button", name="Search").click()

                    # Wait for table refresh
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)  # Grace period for JS table render

                # --- STEP 4: EXTRACT DATA ---
                # Select all rows in the results table
                rows = page.locator("table[summary='Search Results'] > tbody > tr").all()
                print(f"Found {len(rows)} rows in search results.")

                new_opps_count = 0

                for row in rows:
                    try:
                        cells = row.locator("td").all()
                        # Ensure row has enough columns (skipping headers/empty rows)
                        if len(cells) < 5:
                            continue

                        # Column Mapping (Based on Video):
                        # Col 1 (Index 1): Description / Title
                        # Col 2 (Index 2): Department
                        # Col 3 (Index 3): Solicitation Number (e.g., "RFB-758-2500000223-1")
                        # Col 4 (Index 4): Closing Date

                        description_raw = cells[1].inner_text().strip()
                        solicitation_raw = cells[3].inner_text().strip()
                        date_raw = cells[4].inner_text().strip()

                        # Clean Solicitation ID (remove newlines if any)
                        solicitation_number = solicitation_raw.split('\n')[0].strip()

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
                        close_date = self.parse_date(date_raw)
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
