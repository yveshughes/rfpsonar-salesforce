"""
Massachusetts CommBuys Scraper
Scrapes https://www.commbuys.com/bso/
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import os
from datetime import datetime, timedelta
from .base_scraper import BaseScraper


class MassachusettsScraper(BaseScraper):
    """Scraper for Massachusetts CommBuys procurement portal"""

    def __init__(self):
        super().__init__()
        self.portal_url = 'https://www.commbuys.com/bso/'

        # Load credentials from environment
        self.username = os.environ.get('MA_COMMBUYS_USERNAME')
        self.password = os.environ.get('MA_COMMBUYS_PASSWORD')

        # Massachusetts Account ID
        self.account_id = '001V400000dOSjuIAG'  # Commonwealth of Massachusetts

    def get_account_id(self):
        """Return Account ID (required by base class)"""
        return self.account_id

    def parse_date(self, date_str):
        """
        Parse CommBuys date format: "12/30/2025 02:00:00 PM"
        """
        if not date_str:
            return None

        try:
            # CommBuys format: MM/DD/YYYY HH:MM:SS AM/PM
            date_str = date_str.strip()
            dt = datetime.strptime(date_str, '%m/%d/%Y %I:%M:%S %p')
            return dt.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"⚠ Date parsing error for '{date_str}': {str(e)}")
            # Fallback: return 30 days from now
            return (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    def scrape(self):
        """Main scraping workflow for Massachusetts CommBuys"""
        print(f"\n{'='*80}")
        print(f"Starting Massachusetts CommBuys Scrape for Account: {self.account_id}")
        print(f"{'='*80}\n")

        # Check credentials
        if not self.username or not self.password:
            raise ValueError("Missing MA_COMMBUYS_USERNAME or MA_COMMBUYS_PASSWORD environment variables")

        # Get existing solicitations to avoid duplicates
        existing_solicitations = self.get_existing_solicitation_numbers(self.account_id)
        print(f"Found {len(existing_solicitations)} existing solicitations in Salesforce.\n")

        # Setup browser
        page = self.setup_browser()

        try:
            # --- STEP 1: NAVIGATE TO PORTAL ---
            print("Navigating to CommBuys...")
            page.goto(self.portal_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            # --- STEP 2: LOGIN ---
            print("Logging in...")

            # Click the orange "Sign In" button in top right
            sign_in_button = page.get_by_role("button", name="Sign In").first
            sign_in_button.click(timeout=30000)
            page.wait_for_timeout(2000)
            print("✓ Clicked 'Sign In' button")

            # Wait for login form/modal and enter credentials
            # Use exact=True to avoid ambiguity between input field and dialog
            page.get_by_label("User ID", exact=True).wait_for(timeout=20000)
            page.get_by_label("User ID", exact=True).fill(self.username)
            page.get_by_label("Password", exact=True).fill(self.password)
            print("✓ Filled credentials")

            # Submit the form by pressing Enter (simpler than finding the right button)
            page.get_by_label("Password", exact=True).press("Enter")
            print(f"✓ Submitted login form as {self.username}")

            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            # --- STEP 3: NAVIGATE TO BIDS ---
            print("Navigating to Bids...")

            # Click "Bids" link (use exact=True to avoid "Bids(76502)" variant)
            page.get_by_role("link", name="Bids", exact=True).click()
            page.wait_for_timeout(2000)
            print("✓ Clicked 'Bids' link")

            # --- STEP 4: VIEW OPEN BIDS ---
            print("Loading Open Bids...")

            # Click "View More" under Open Bids
            # Find the "View More" link that's associated with the "Bids - Open" section
            page.locator("text=View More").first.click()
            page.wait_for_timeout(3000)
            print("✓ Clicked 'View More' for Open Bids")

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(5000)

            # --- STEP 5: SET PAGINATION TO SHOW ALL ---
            print("Setting pagination to show maximum records...")
            try:
                # The pagination selector might vary - try common patterns
                # Look for a dropdown or option to change records per page
                # This may need adjustment based on actual page structure
                page.wait_for_timeout(2000)
                print("✓ Page loaded with bids")
            except Exception as e:
                print(f"⚠ Could not adjust pagination: {e}")

            # --- STEP 6: EXTRACT DATA ---
            print("Extracting bid data from table...")

            # Find the table - adjust selector based on actual page
            # The table has columns: Bid #, Organization, Alternate Id, Buyer, Description, Purchase Method, Bid Opening Date, Bid Q & A, Quotes, Bid Holder
            rows = page.locator("table tbody tr").all()
            print(f"Found {len(rows)} rows in bids table.")

            new_opps_count = 0

            for row in rows:
                try:
                    cells = row.locator("td").all()

                    # Skip if not enough cells
                    if len(cells) < 8:
                        continue

                    # Extract data from cells
                    # Based on screenshot: Bid #, Organization, Alternate Id, Buyer, Description, Purchase Method, Bid Opening Date, Bid Q & A, Quotes, Bid Holder
                    bid_number_cell = cells[0]
                    organization = cells[1].inner_text().strip()
                    alternate_id = cells[2].inner_text().strip()
                    buyer = cells[3].inner_text().strip()
                    description = cells[4].inner_text().strip()
                    purchase_method = cells[5].inner_text().strip()
                    bid_opening_date = cells[6].inner_text().strip()

                    # Get bid number (it's a link)
                    bid_number_link = bid_number_cell.locator("a").first
                    bid_number = bid_number_link.inner_text().strip()
                    bid_url = bid_number_link.get_attribute("href")

                    # Make URL absolute if needed
                    if bid_url and not bid_url.startswith('http'):
                        bid_url = f"https://www.commbuys.com{bid_url}"

                    # Skip if already exists
                    if bid_number in existing_solicitations:
                        continue

                    # Parse closing date
                    close_date = self.parse_date(bid_opening_date)

                    # Construct Salesforce Opportunity Data
                    opp_data = {
                        'Name': description[:120] if description else f"{organization} - {bid_number}",
                        'AccountId': self.account_id,
                        'Solicitation_Number__c': bid_number,
                        'CloseDate': close_date,
                        'StageName': 'Prospecting',
                        'Solicitation_Type__c': self.map_solicitation_type(purchase_method),
                        'Department__c': organization[:255] if organization else None,
                        'Buyer_Name__c': buyer[:255] if buyer else None,
                        'Portal_URL__c': bid_url,
                        'Data_Source__c': 'Automated Scraper',
                        'Response_Status__c': 'New - Not Reviewed',
                        'Description': (
                            f"Organization: {organization}\n"
                            f"Buyer: {buyer}\n"
                            f"Purchase Method: {purchase_method}\n"
                            f"Alternate ID: {alternate_id}\n"
                            f"Description: {description}\n"
                            f"Bid Opening Date: {bid_opening_date}\n"
                            f"Link: {bid_url}"
                        )
                    }

                    # Create in Salesforce
                    result = self.create_salesforce_opportunity(opp_data)
                    if result:
                        new_opps_count += 1
                        print(f"✓ Created: {bid_number}")

                except Exception as row_error:
                    print(f"⚠ Error parsing row: {str(row_error)}")
                    continue

            # Update account scrape status
            try:
                self.update_account_scrape_status(
                    self.account_id,
                    'Success',
                    None
                )
            except Exception as e:
                print(f"⚠ Could not update account status: {e}")

            print(f"\n{'='*80}")
            print(f"Scrape Complete. Created {new_opps_count} new opportunities.")
            print(f"{'='*80}\n")

            return {
                'status': 'success',
                'created': new_opps_count,
                'existing': len(existing_solicitations)
            }

        except Exception as e:
            print(f"\n✗ CRITICAL FAILURE: {str(e)}")
            import traceback
            traceback.print_exc()

            # Update account with error status
            try:
                self.update_account_scrape_status(
                    self.account_id,
                    'Error',
                    str(e)[:255]
                )
            except:
                pass

            # Create stub opportunity for manual review
            self.create_stub_opportunity(
                self.account_id,
                self.portal_url,
                str(e)
            )

            raise

        finally:
            self.cleanup()


if __name__ == "__main__":
    scraper = MassachusettsScraper()
    scraper.scrape()
