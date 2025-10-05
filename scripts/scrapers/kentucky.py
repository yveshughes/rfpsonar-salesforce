"""
Kentucky eMars Portal Scraper
Inherits from BaseScraper
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import time
import os
from .base_scraper import BaseScraper


class KentuckyScraper(BaseScraper):
    """Scraper for Kentucky eMars procurement portal"""

    def __init__(self):
        super().__init__()
        self.username = os.environ.get('KY_PORTAL_USERNAME')
        self.password = os.environ.get('KY_PORTAL_PASSWORD')
        self.login_url = "https://vss.ky.gov/vssprod-ext/Advantage4"
        self.account_id = '001V400000dOSjKIAW'  # Commonwealth of Kentucky

    def get_account_id(self):
        """Return Kentucky Account ID"""
        return self.account_id

    def login(self):
        """Login to Kentucky eMars portal"""
        self.page.goto(self.login_url)
        self.page.fill("#username", self.username)
        self.page.fill("#password", self.password)
        self.page.click("#loginButton")
        self.page.wait_for_load_state('networkidle')
        print("✓ Kentucky: Logged in")

    def navigate_to_solicitations(self):
        """Navigate to Published Solicitations page"""
        self.page.click("text=Published Solicitations")
        self.page.wait_for_load_state('networkidle')
        print("✓ Kentucky: Navigated to solicitations")

    def sort_by_closing_date(self):
        """Sort by closing date"""
        self.page.click("th:has-text('Closing Date and Time/Status')")
        time.sleep(2)
        print("✓ Kentucky: Sorted by closing date")

    def get_solicitation_links(self):
        """Extract all solicitation links"""
        # Wait for table to load
        self.page.wait_for_selector("table tr td")

        # Get all links to solicitation details
        links = []
        rows = self.page.query_selector_all("table tr:has(td)")

        for row in rows:
            try:
                link_element = row.query_selector("a[href*='Solicitation']")
                if link_element:
                    href = link_element.get_attribute('href')
                    links.append(href)
            except:
                continue

        print(f"✓ Kentucky: Found {len(links)} solicitations")
        return links

    def scrape_solicitation_detail(self, link):
        """Scrape individual solicitation"""
        self.page.goto(link)
        self.page.wait_for_load_state('networkidle')

        data = {'portal_url': link}

        try:
            # Wait for the details table to load
            self.page.wait_for_selector("td:has-text('Solicitation Number')")

            # Helper function to safely get text content
            def get_field_value(label):
                try:
                    selector = f"td:has-text('{label}') + td"
                    element = self.page.query_selector(selector)
                    return element.inner_text().strip() if element else ""
                except:
                    return ""

            data['solicitation_number'] = get_field_value('Solicitation Number')
            data['description'] = get_field_value('Description')
            data['buyer_name'] = get_field_value('Buyer Name')
            data['buyer_email'] = get_field_value('Buyer Email')
            data['buyer_phone'] = get_field_value('Buyer Phone')
            data['department'] = get_field_value('Department')
            data['closing_date'] = get_field_value('Closing Date')
            data['solicitation_type'] = get_field_value('Type')
            data['category'] = get_field_value('Category')

            # Attachments
            try:
                # Click attachments tab if it exists
                attach_tab = self.page.query_selector("a:has-text('Attachments')")
                if attach_tab:
                    attach_tab.click()
                    time.sleep(1)

                    attachments = []
                    file_rows = self.page.query_selector_all("#attachmentsTable tr:has(td)")

                    for row in file_rows:
                        try:
                            file_link = row.query_selector("a")
                            if file_link:
                                attachments.append({
                                    'name': file_link.inner_text().strip(),
                                    'url': file_link.get_attribute('href')
                                })
                        except:
                            continue

                    data['attachments'] = attachments
                else:
                    data['attachments'] = []
            except:
                data['attachments'] = []

        except Exception as e:
            print(f"✗ Kentucky: Error scraping {link}: {str(e)}")
            data['error'] = str(e)

        return data

    def scrape(self):
        """Main scrape execution"""
        print("Starting Kentucky scrape...")

        try:
            self.setup_browser()

            # Get existing solicitations
            existing = self.get_existing_solicitation_numbers(self.account_id)
            print(f"Kentucky: {len(existing)} existing opportunities")

            # Login and navigate
            self.login()
            self.navigate_to_solicitations()
            self.sort_by_closing_date()

            # Get all links
            links = self.get_solicitation_links()

            new_opportunities = []

            # Scrape each
            for i, link in enumerate(links, 1):
                print(f"\nKentucky [{i}/{len(links)}]: {link}")
                data = self.scrape_solicitation_detail(link)

                # Skip duplicates
                if data.get('solicitation_number') in existing:
                    print(f"  → Already exists")
                    continue

                # Create opportunity
                sf_opp = {
                    'AccountId': self.account_id,
                    'Name': data.get('description', '')[:80],
                    'Solicitation_Number__c': data.get('solicitation_number'),
                    'Solicitation_Type__c': self.map_solicitation_type(data.get('solicitation_type')),
                    'CloseDate': self.parse_closing_date(data.get('closing_date')),
                    'StageName': 'Prospecting',
                    'Department__c': data.get('department'),
                    'Buyer_Name__c': data.get('buyer_name'),
                    'Buyer_Email__c': data.get('buyer_email'),
                    'Buyer_Phone__c': data.get('buyer_phone'),
                    'RFP_Category__c': self.map_category(data.get('category')),
                    'Response_Status__c': 'New - Not Reviewed',
                    'Portal_URL__c': data.get('portal_url')
                }

                result = self.create_salesforce_opportunity(sf_opp)
                if result:
                    print(f"  ✓ Created: {result['id']}")
                    new_opportunities.append(data)

            return {
                'success': True,
                'total_found': len(links),
                'new_created': len(new_opportunities),
                'opportunities': new_opportunities
            }

        except Exception as e:
            print(f"✗ Kentucky: Fatal error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

        finally:
            self.cleanup()
