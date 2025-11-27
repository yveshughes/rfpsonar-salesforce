"""
Puerto Rico Procurement Scraper
Scrapes https://recuperacion.pr.gov/en/procurement-and-nofa/procurement/
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import os
from datetime import datetime, timedelta
from .base_scraper import BaseScraper


class PuertoRicoScraper(BaseScraper):
    """Scraper for Puerto Rico procurement portal"""

    def __init__(self):
        super().__init__()
        self.portal_url = 'https://recuperacion.pr.gov/en/procurement-and-nofa/procurement/'

        # Puerto Rico Account ID
        self.account_id = '001V400000dOSjtIAG'  # Commonwealth of Puerto Rico

    def get_account_id(self):
        """Return Account ID (required by base class)"""
        return self.account_id

    def parse_date(self, date_str):
        """
        Parse date from Puerto Rico portal
        Handles various formats
        """
        if not date_str:
            return None

        try:
            date_str = date_str.strip()

            # Try common formats
            for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%B %d, %Y', '%b %d, %Y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except:
                    continue

            # If all formats fail, return 30 days from now as fallback
            return (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        except Exception as e:
            print(f"⚠ Date parsing error for '{date_str}': {str(e)}")
            return (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    def scrape(self):
        """Main scraping workflow for Puerto Rico"""
        print(f"\n{'='*80}")
        print(f"Starting Puerto Rico Procurement Scrape for Account: {self.account_id}")
        print(f"{'='*80}\n")

        # Get existing solicitations to avoid duplicates
        existing_solicitations = self.get_existing_solicitation_numbers(self.account_id)
        print(f"Found {len(existing_solicitations)} existing solicitations in Salesforce.\n")

        # Setup browser
        page = self.setup_browser()

        try:
            # --- STEP 1: NAVIGATE TO PORTAL ---
            print("Navigating to Puerto Rico procurement portal...")
            page.goto(self.portal_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # --- STEP 2: SELECT "ACTIVE" STATUS ---
            print("Filtering for Active procurements...")

            # Look for Status dropdown - common selectors
            try:
                # Try to find status dropdown by label
                status_dropdown = None

                # Method 1: Look for <select> element with name/id containing "status"
                try:
                    status_dropdown = page.locator("select[name*='status' i], select[id*='status' i]").first
                    status_dropdown.wait_for(state="visible", timeout=5000)
                    print("  ✓ Found status dropdown by name/id")
                except:
                    pass

                # Method 2: Look for label containing "Status" and find associated select
                if not status_dropdown:
                    try:
                        # Find label with text "Status" and get its 'for' attribute
                        label = page.locator("label:has-text('Status')").first
                        label_for = label.get_attribute("for", timeout=3000)
                        if label_for:
                            status_dropdown = page.locator(f"select#{label_for}")
                            print("  ✓ Found status dropdown by label association")
                    except:
                        pass

                # Method 3: Generic select dropdown search
                if not status_dropdown:
                    # Find all select elements and check their options
                    selects = page.locator("select").all()
                    for select in selects:
                        try:
                            options_text = select.inner_text(timeout=1000).lower()
                            if 'active' in options_text and ('closed' in options_text or 'pending' in options_text):
                                status_dropdown = select
                                print("  ✓ Found status dropdown by analyzing options")
                                break
                        except:
                            continue

                if status_dropdown:
                    # Select "Active" option
                    status_dropdown.select_option(label="Active")
                    print("  ✓ Selected 'Active' status")
                    page.wait_for_timeout(2000)
                    page.wait_for_load_state("networkidle")
                else:
                    print("  ⚠ Could not find status dropdown - proceeding with default view")

            except Exception as e:
                print(f"  ⚠ Could not set status filter: {e}")
                print("  Proceeding with default view...")

            # --- STEP 3: EXTRACT DATA ---
            print("Extracting procurement data...")

            all_opportunities = []
            total_new_opps = 0
            page_num = 1

            # Try multiple table/list selectors
            # Look for common patterns: tables, cards, list items
            rows = []

            # Pattern 1: Traditional table
            try:
                rows = page.locator("table tbody tr").all()
                if len(rows) > 0:
                    print(f"  Found {len(rows)} rows in table")
            except:
                pass

            # Pattern 2: Div-based rows (Bootstrap, Tailwind, etc.)
            if len(rows) == 0:
                try:
                    rows = page.locator(".row.procurement-item, .procurement-row, [class*='procurement']").all()
                    if len(rows) > 0:
                        print(f"  Found {len(rows)} procurement items (div-based)")
                except:
                    pass

            # Pattern 3: List items
            if len(rows) == 0:
                try:
                    rows = page.locator("ul.procurement-list li, .procurement-list > div").all()
                    if len(rows) > 0:
                        print(f"  Found {len(rows)} procurement items (list-based)")
                except:
                    pass

            if len(rows) == 0:
                print("  ⚠ No procurement rows found - page structure may be different")
                # Take a screenshot for debugging
                page.screenshot(path="/tmp/puerto_rico_debug.png")
                print("  Saved screenshot to /tmp/puerto_rico_debug.png for debugging")

                # Try to extract any text that looks like opportunities
                page_content = page.content()
                print("\n  Page structure analysis needed. Creating stub for manual review...")

                # Update status and create stub
                self.update_account_scrape_status(
                    self.account_id,
                    'Failed',
                    'Could not find procurement data - page structure needs analysis'
                )

                self.create_stub_opportunity(
                    self.account_id,
                    self.portal_url,
                    'Could not find procurement data - page structure needs analysis'
                )

                return {
                    'status': 'failed',
                    'created': 0,
                    'existing': len(existing_solicitations),
                    'error': 'Could not find procurement rows'
                }

            # Process each row/item
            for idx, row in enumerate(rows):
                try:
                    # Extract data - adjust selectors based on actual page structure
                    # Common fields: solicitation number, title/description, due date, category

                    solicitation_number = None
                    title = None
                    description = None
                    due_date = None
                    category = None
                    url = None

                    # Try to extract solicitation number (common patterns)
                    try:
                        for selector in ["td:nth-child(1)", ".solicitation-number", "[class*='number']", "a[href*='procurement']"]:
                            try:
                                elem = row.locator(selector).first
                                text = elem.inner_text(timeout=1000).strip()
                                if text and len(text) < 50:  # Reasonable length for a number
                                    solicitation_number = text
                                    # Try to get URL if it's a link
                                    if elem.evaluate("el => el.tagName") == "A":
                                        url = elem.get_attribute("href")
                                    break
                            except:
                                continue
                    except:
                        pass

                    # If no solicitation number, use row index as unique identifier
                    if not solicitation_number:
                        solicitation_number = f"PR-{datetime.now().strftime('%Y%m%d')}-{idx+1}"

                    # Extract title/description
                    try:
                        for selector in ["td:nth-child(2)", ".title", ".description", "h3", "h4", "strong"]:
                            try:
                                text = row.locator(selector).first.inner_text(timeout=1000).strip()
                                if text and len(text) > 10:
                                    title = text
                                    break
                            except:
                                continue

                        # If no title found, use full row text
                        if not title:
                            title = row.inner_text(timeout=1000).strip()[:120]
                    except:
                        title = f"Puerto Rico Procurement {solicitation_number}"

                    # Extract due date
                    try:
                        for selector in [".due-date", ".deadline", "[class*='date']", "td:nth-child(3)"]:
                            try:
                                date_text = row.locator(selector).first.inner_text(timeout=1000).strip()
                                if date_text:
                                    due_date = self.parse_date(date_text)
                                    if due_date:
                                        break
                            except:
                                continue
                    except:
                        pass

                    # Default due date if not found
                    if not due_date:
                        due_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

                    # Make URL absolute if needed
                    if url and not url.startswith('http'):
                        if url.startswith('/'):
                            url = f"https://recuperacion.pr.gov{url}"
                        else:
                            url = f"https://recuperacion.pr.gov/{url}"

                    # Skip if already exists
                    if solicitation_number in existing_solicitations:
                        continue

                    # Construct Salesforce Opportunity Data
                    opp_data = {
                        'Name': title[:120] if title else f"PR Procurement - {solicitation_number}",
                        'AccountId': self.account_id,
                        'Solicitation_Number__c': solicitation_number,
                        'CloseDate': due_date,
                        'StageName': 'Prospecting',
                        'Solicitation_Type__c': 'Other',
                        'Portal_URL__c': url if url else self.portal_url,
                        'Data_Source__c': 'Automated Scraper',
                        'Response_Status__c': 'New - Not Reviewed',
                        'Description': (
                            f"Title: {title}\n"
                            f"Solicitation Number: {solicitation_number}\n"
                            f"Due Date: {due_date}\n"
                            f"Link: {url if url else self.portal_url}\n"
                            f"\nSource: Puerto Rico Procurement Portal"
                        )
                    }

                    # Create in Salesforce
                    result = self.create_salesforce_opportunity(opp_data)
                    if result:
                        total_new_opps += 1
                        print(f"✓ Created: {solicitation_number} - {title[:50]}")

                except Exception as row_error:
                    print(f"⚠ Error parsing row {idx}: {str(row_error)}")
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
            print(f"Scrape Complete. Created {total_new_opps} new opportunities.")
            print(f"{'='*80}\n")

            return {
                'status': 'success',
                'created': total_new_opps,
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
                    'Failed',
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
    scraper = PuertoRicoScraper()
    scraper.scrape()
