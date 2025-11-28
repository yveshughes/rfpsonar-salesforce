"""
Virginia Procurement Scraper
Scrapes https://mvendor.cgieva.com/Vendor/public/AllOpportunities.jsp
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import os
from datetime import datetime, timedelta
from .base_scraper import BaseScraper


class VirginiaScraper(BaseScraper):
    """Scraper for Virginia eVA procurement portal"""

    def __init__(self):
        super().__init__()
        self.portal_url = 'https://mvendor.cgieva.com/Vendor/public/AllOpportunities.jsp'

        # Virginia Account ID
        self.account_id = '001V400000dOSjnIAG'  # Commonwealth of Virginia

    def get_account_id(self):
        """Return Account ID (required by base class)"""
        return self.account_id

    def parse_date(self, date_str):
        """
        Parse date from Virginia portal
        Handles various formats like MM/DD/YYYY, MM-DD-YYYY
        """
        if not date_str:
            return None

        try:
            date_str = date_str.strip()

            # Try common formats
            for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%m/%d/%y']:
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
        """Main scraping workflow for Virginia eVA"""
        print(f"\n{'='*80}")
        print(f"Starting Virginia eVA Procurement Scrape for Account: {self.account_id}")
        print(f"{'='*80}\n")

        # Get existing solicitations to avoid duplicates
        existing_solicitations = self.get_existing_solicitation_numbers(self.account_id)
        print(f"Found {len(existing_solicitations)} existing solicitations in Salesforce.\n")

        # Setup browser
        page = self.setup_browser()

        try:
            # --- STEP 1: NAVIGATE TO PORTAL ---
            print("Navigating to Virginia eVA portal...")
            page.goto(self.portal_url, timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            # Check if we were redirected or if there's a login page
            current_url = page.url
            print(f"  Current URL: {current_url}")

            # --- STEP 2: WAIT FOR CONTENT TO LOAD ---
            print("Waiting for opportunities to load...")

            # Wait for the opportunities grid to appear
            page.wait_for_timeout(5000)

            # Scroll down to trigger lazy loading of opportunities
            print("  Scrolling to load opportunities...")
            for i in range(3):
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(2000)

            # Wait for results text to appear
            try:
                page.wait_for_selector("text=/Found \\d+ results/", timeout=10000)
                results_text = page.locator("text=/Found \\d+ results/").first.inner_text()
                print(f"  {results_text}")
            except:
                print("  Could not find results count")

            # --- STEP 3: EXTRACT DATA ---
            print("Extracting procurement data...")

            total_new_opps = 0
            rows = []

            # eVA uses .card elements for each opportunity
            # Each card contains: title, status, solicitation number, entity, description, closing date
            try:
                all_cards = page.locator(".card").all()
                print(f"  Found {len(all_cards)} .card elements")

                # Filter to only opportunity cards (not other UI cards)
                for card in all_cards:
                    try:
                        card_text = card.inner_text(timeout=2000)
                        # Check if it contains opportunity-like content
                        if ("Status:" in card_text and
                            any(pattern in card_text for pattern in ["IFB", "RFP", "RFQ", "ITB", "RFS"])):
                            rows.append(card)
                    except:
                        continue

                print(f"  Filtered to {len(rows)} opportunity cards")

            except Exception as e:
                print(f"  ⚠ Error finding cards: {e}")

            if len(rows) == 0:
                print("  ⚠ No opportunity rows found")

                # Take screenshot for debugging
                try:
                    page.screenshot(path="/tmp/virginia_debug.png")
                    print("  Saved screenshot to /tmp/virginia_debug.png")
                except:
                    pass

                # Check page content
                page_text = page.inner_text("body")
                print(f"\n  Page content preview (first 500 chars):\n  {page_text[:500]}\n")

                # Update status and create stub
                self.update_account_scrape_status(
                    self.account_id,
                    'Failed',
                    None
                )

                self.create_stub_opportunity(
                    self.account_id,
                    self.portal_url,
                    'Could not find opportunity data - page structure needs analysis'
                )

                return {
                    'status': 'failed',
                    'created': 0,
                    'existing': len(existing_solicitations),
                    'error': 'Could not find opportunity rows'
                }

            # Process each row/item
            print(f"\nProcessing {len(rows)} opportunity cards...")
            for idx, row in enumerate(rows):
                try:
                    # Get row text
                    row_text = row.inner_text(timeout=5000).strip()

                    #  Skip empty rows
                    if not row_text or len(row_text) < 10:
                        continue

                    # Extract data - adjust selectors based on actual page structure
                    solicitation_number = None
                    title = None
                    description = None
                    due_date = None
                    category = None
                    url = None

                    # First, try to extract from the container structure
                    # Look for key elements: title, solicitation number, due date, status

                    # Extract solicitation number - look for patterns like "IFB 107443-1", "RFP 12345", etc.
                    import re
                    try:
                        # Common patterns: IFB, RFP, RFQ followed by number
                        number_match = re.search(r'(IFB|RFP|RFQ|ITB|RFS|RFPQ)\s*[\d\-]+', row_text, re.IGNORECASE)
                        if number_match:
                            solicitation_number = number_match.group(0)
                    except:
                        pass

                    # Extract title - usually the first line or largest text
                    try:
                        # Try to find heading or first significant text
                        headings = row.locator("h1, h2, h3, h4, h5, h6").all()
                        if len(headings) > 0:
                            title = headings[0].inner_text(timeout=1000).strip()
                        else:
                            # Get first line of text
                            lines = row_text.split('\n')
                            for line in lines:
                                if len(line.strip()) > 10 and line.strip().lower() not in ['status:', 'open', 'closed', 'awarded']:
                                    title = line.strip()
                                    break
                    except:
                        pass

                    # Extract status
                    status = None
                    try:
                        status_match = re.search(r'Status:\s*(\w+)', row_text, re.IGNORECASE)
                        if status_match:
                            status = status_match.group(1)
                    except:
                        pass

                    # Filter: Only process "Open" opportunities
                    if status and status.lower() != 'open':
                        continue

                    # Extract due date - look for date patterns
                    try:
                        # Look for date elements or text
                        date_elements = row.locator("text=/\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/").all()
                        if len(date_elements) > 0:
                            date_text = date_elements[0].inner_text(timeout=1000)
                            due_date = self.parse_date(date_text)
                    except:
                        pass

                    # Get URL if there's a link
                    try:
                        links = row.locator("a").all()
                        if len(links) > 0:
                            url = links[0].get_attribute("href", timeout=1000)
                    except:
                        pass

                    # Fallback: Check if it's a table row structure
                    cells = row.locator("td, th").all()

                    if len(cells) >= 3 and not solicitation_number:
                        # Table-based structure
                        # Typical columns: Number, Title, Due Date, etc.
                        try:
                            # Try to get solicitation number from first cell
                            cell_0_text = cells[0].inner_text(timeout=1000).strip()
                            if cell_0_text and len(cell_0_text) < 50:
                                solicitation_number = cell_0_text

                            # Check if there's a link in the first few cells
                            for i in range(min(3, len(cells))):
                                try:
                                    link = cells[i].locator("a").first
                                    url = link.get_attribute("href", timeout=1000)
                                    if not solicitation_number:
                                        solicitation_number = link.inner_text(timeout=1000).strip()
                                    break
                                except:
                                    continue

                            # Get title (usually 2nd or 3rd column)
                            if len(cells) > 1:
                                title = cells[1].inner_text(timeout=1000).strip()

                            # Try to find due date (look for date patterns)
                            for cell in cells:
                                try:
                                    cell_text = cell.inner_text(timeout=1000).strip()
                                    # Check if it looks like a date
                                    if '/' in cell_text or '-' in cell_text:
                                        parsed = self.parse_date(cell_text)
                                        if parsed:
                                            due_date = parsed
                                            break
                                except:
                                    continue

                        except Exception as e:
                            print(f"  ⚠ Error parsing table row {idx}: {e}")
                            continue
                    else:
                        # Non-table structure - try generic extraction
                        try:
                            # Look for links
                            links = row.locator("a").all()
                            if len(links) > 0:
                                url = links[0].get_attribute("href", timeout=1000)
                                title = links[0].inner_text(timeout=1000).strip()

                            # Use row text as fallback
                            if not title:
                                title = row_text[:120]

                            # Try to find anything that looks like a number
                            words = row_text.split()
                            for word in words:
                                if len(word) > 5 and any(c.isdigit() for c in word):
                                    solicitation_number = word
                                    break

                        except Exception as e:
                            print(f"  ⚠ Error parsing non-table row {idx}: {e}")
                            continue

                    # Generate solicitation number if not found
                    if not solicitation_number:
                        solicitation_number = f"VA-{datetime.now().strftime('%Y%m%d')}-{idx+1}"

                    # Generate title if not found
                    if not title or len(title) < 10:
                        title = f"Virginia Opportunity {solicitation_number}"

                    # Default due date if not found
                    if not due_date:
                        due_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

                    # Make URL absolute if needed
                    if url and not url.startswith('http'):
                        if url.startswith('/'):
                            url = f"https://mvendor.cgieva.com{url}"
                        else:
                            url = f"https://mvendor.cgieva.com/Vendor/public/{url}"

                    # Skip if already exists
                    if solicitation_number in existing_solicitations:
                        continue

                    # Construct Salesforce Opportunity Data
                    opp_data = {
                        'Name': title[:120] if title else f"VA Procurement - {solicitation_number}",
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
                            f"\nSource: Virginia eVA Portal"
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
    scraper = VirginiaScraper()
    scraper.scrape()
