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

            # Click "Bids" link - look for the one with a count like "Bids(76502)"
            # This is the actual navigation link in the top menu
            try:
                # First try to find the link with a number (e.g., "Bids(76502)")
                bids_link = page.get_by_role("link").filter(has_text="Bids(")
                bids_link.wait_for(state="visible", timeout=30000)
                bids_link.click()
                print("✓ Clicked 'Bids' link with count")
            except Exception as e:
                # Fallback: just click any "Bids" link
                print(f"  Fallback: trying simple 'Bids' selector ({e})")
                page.get_by_role("link", name="Bids").first.click()
                print("✓ Clicked 'Bids' link")

            page.wait_for_timeout(2000)

            # --- STEP 4: VIEW OPEN BIDS ---
            print("Loading Open Bids...")

            # Click "View More" under Open Bids
            # Find the "View More" link that's associated with the "Bids - Open" section
            page.locator("text=View More").first.click()
            page.wait_for_timeout(3000)
            print("✓ Clicked 'View More' for Open Bids")

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(5000)

            # --- STEP 5: SET PAGINATION TO SHOW ALL RECORDS ---
            print("Setting pagination to show all records...")

            # Look for pagination info like "1-25 of 584" to understand total count
            try:
                pagination_text = page.locator("text=/\\d+-\\d+ of \\d+/").first.inner_text(timeout=5000)
                print(f"     Pagination info: {pagination_text}")

                # Try to find and click a link/button to show more records per page
                # Common patterns: "100", "200", "Show All", or a dropdown
                try:
                    # Look for a "100" or "200" link to increase records per page
                    page.get_by_text("100", exact=True).click(timeout=3000)
                    print("     ✓ Set to show 100 records per page")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)
                except:
                    try:
                        # Try "200" if "100" doesn't exist
                        page.get_by_text("200", exact=True).click(timeout=3000)
                        print("     ✓ Set to show 200 records per page")
                        page.wait_for_load_state("networkidle")
                        page.wait_for_timeout(3000)
                    except:
                        print("     ⚠ Could not find pagination controls - will process page by page")

            except Exception as e:
                print(f"     ⚠ Could not get pagination info: {e}")

            # --- STEP 6: EXTRACT DATA FROM ALL PAGES ---
            print("Extracting bid data from all pages...")

            all_opportunities = []
            total_new_opps = 0
            page_num = 1

            while True:
                print(f"Processing page {page_num}...")

                # Find the table - adjust selector based on actual page
                # The table has columns: Bid #, Organization, Alternate Id, Buyer, Description, Purchase Method, Bid Opening Date, Bid Q & A, Quotes, Bid Holder
                rows = page.locator("table tbody tr").all()
                print(f"  Found {len(rows)} rows on page {page_num}")

                for row in rows:
                    try:
                        cells = row.locator("td").all()

                        # Skip if not enough cells
                        if len(cells) < 8:
                            continue

                        # Extract data from cells
                        # Based on screenshot: Bid #, Organization, Alternate Id, Buyer, Description, Purchase Method, Bid Opening Date, Bid Q & A, Quotes, Bid Holder
                        bid_number_cell = cells[0]

                        # Skip rows that don't have a link in first cell (header/pagination rows)
                        try:
                            bid_number_link = bid_number_cell.locator("a").first
                            bid_number = bid_number_link.inner_text(timeout=1000).strip()
                            bid_url = bid_number_link.get_attribute("href")
                        except:
                            # No link found - skip this row (probably header or pagination)
                            continue

                        organization = cells[1].inner_text().strip()
                        alternate_id = cells[2].inner_text().strip()
                        buyer = cells[3].inner_text().strip()
                        description = cells[4].inner_text().strip()
                        purchase_method = cells[5].inner_text().strip()
                        bid_opening_date = cells[6].inner_text().strip()

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
                            total_new_opps += 1
                            print(f"✓ Created: {bid_number}")

                    except Exception as row_error:
                        print(f"⚠ Error parsing row: {str(row_error)}")
                        continue

                # After processing all rows on current page, check for next page
                print(f"  Completed page {page_num}")

                # Look for "Next" button or next page number
                try:
                    # Try to find and click the "Next" button/link (represented by ›)
                    next_button = page.locator("a").filter(has_text="›").or_(page.get_by_role("link", name="Next"))

                    if next_button.is_visible(timeout=2000):
                        print(f"  Navigating to page {page_num + 1}...")
                        next_button.click()
                        page.wait_for_load_state("networkidle")
                        page.wait_for_timeout(3000)
                        page_num += 1
                    else:
                        print("  No more pages - pagination complete")
                        break
                except Exception as e:
                    print(f"  No next page found - completed all pages: {e}")
                    break

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
            print(f"Scrape Complete. Created {total_new_opps} new opportunities across {page_num} page(s).")
            print(f"{'='*80}\n")

            return {
                'status': 'success',
                'created': total_new_opps,
                'existing': len(existing_solicitations),
                'pages_processed': page_num
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
