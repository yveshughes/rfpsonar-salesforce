"""
Kentucky eMars Portal Scraper
Inherits from BaseScraper
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
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
        self.driver.get(self.login_url)
        self.wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(self.username)
        self.wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(self.password)
        self.wait.until(EC.element_to_be_clickable((By.ID, "loginButton"))).click()
        self.wait.until(EC.title_contains("Home Page"))
        print("✓ Kentucky: Logged in")

    def navigate_to_solicitations(self):
        """Navigate to Published Solicitations page"""
        self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Published Solicitations"))).click()
        self.wait.until(EC.title_contains("Published Solicitations"))
        print("✓ Kentucky: Navigated to solicitations")

    def sort_by_closing_date(self):
        """Sort by closing date"""
        closing_col = self.driver.find_element(By.XPATH, "//th[contains(text(),'Closing Date and Time/Status')]")
        closing_col.click()
        time.sleep(2)
        print("✓ Kentucky: Sorted by closing date")

    def get_solicitation_links(self):
        """Extract all solicitation links"""
        rows = self.driver.find_elements(By.XPATH, "//table//tr[td]")
        links = []
        for row in rows:
            try:
                link = row.find_element(By.XPATH, ".//a[contains(@href, 'Solicitation')]")
                links.append(link.get_attribute('href'))
            except:
                continue
        print(f"✓ Kentucky: Found {len(links)} solicitations")
        return links

    def scrape_solicitation_detail(self, link):
        """Scrape individual solicitation"""
        self.driver.get(link)
        time.sleep(2)

        data = {'portal_url': link}

        try:
            data['solicitation_number'] = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'Solicitation Number')]/following-sibling::td"))
            ).text.strip()

            data['description'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Description')]/following-sibling::td").text.strip()
            data['buyer_name'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Buyer Name')]/following-sibling::td").text.strip()
            data['buyer_email'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Buyer Email')]/following-sibling::td").text.strip()
            data['buyer_phone'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Buyer Phone')]/following-sibling::td").text.strip()
            data['department'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Department')]/following-sibling::td").text.strip()
            data['closing_date'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Closing Date')]/following-sibling::td").text.strip()
            data['solicitation_type'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Type')]/following-sibling::td").text.strip()
            data['category'] = self.driver.find_element(By.XPATH, "//td[contains(text(),'Category')]/following-sibling::td").text.strip()

            # Attachments
            try:
                attach_tab = self.driver.find_element(By.XPATH, "//a[contains(text(),'Attachments')]")
                attach_tab.click()
                time.sleep(1)

                attachments = []
                file_rows = self.driver.find_elements(By.XPATH, "//table[@id='attachmentsTable']//tr[td]")
                for row in file_rows:
                    try:
                        file_link = row.find_element(By.XPATH, ".//a")
                        attachments.append({
                            'name': file_link.text.strip(),
                            'url': file_link.get_attribute('href')
                        })
                    except:
                        continue
                data['attachments'] = attachments
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
            self.setup_driver()

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
            return {'success': False, 'error': str(e)}

        finally:
            self.cleanup()
