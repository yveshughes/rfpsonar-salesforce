"""
Base scraper class that all jurisdiction scrapers inherit from
"""
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os
import requests
from datetime import datetime


class BaseScraper(ABC):
    """Abstract base class for all procurement portal scrapers"""

    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.sf_api_key = os.environ.get('SALESFORCE_API_KEY')
        self.sf_instance_url = os.environ.get('SALESFORCE_INSTANCE_URL')

    def setup_browser(self):
        """Setup headless Playwright browser"""
        self.playwright = sync_playwright().start()

        # Launch Chromium browser with headless mode
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )

        # Create a new context with custom user agent
        context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

        # Create a new page
        self.page = context.new_page()
        self.page.set_default_timeout(15000)  # 15 seconds timeout

        return self.page

    def cleanup(self):
        """Close browser and cleanup"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    @abstractmethod
    def get_account_id(self):
        """Return Salesforce Account ID for this jurisdiction"""
        pass

    @abstractmethod
    def scrape(self):
        """Main scrape logic - must be implemented by subclass"""
        pass

    def get_existing_solicitation_numbers(self, account_id):
        """Query Salesforce for existing solicitation numbers"""
        headers = {
            'Authorization': f'Bearer {self.sf_api_key}',
            'Content-Type': 'application/json'
        }

        query = f"SELECT Solicitation_Number__c FROM Opportunity WHERE AccountId = '{account_id}'"
        url = f"{self.sf_instance_url}/services/data/v65.0/query/?q={query}"

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            records = response.json().get('records', [])
            return {r['Solicitation_Number__c'] for r in records if r.get('Solicitation_Number__c')}
        return set()

    def create_salesforce_opportunity(self, opportunity_data):
        """Create new opportunity in Salesforce"""
        headers = {
            'Authorization': f'Bearer {self.sf_api_key}',
            'Content-Type': 'application/json'
        }

        url = f"{self.sf_instance_url}/services/data/v65.0/sobjects/Opportunity"
        response = requests.post(url, headers=headers, json=opportunity_data)

        if response.status_code == 201:
            return response.json()
        else:
            print(f"✗ Error creating opportunity: {response.text}")
            return None

    def create_stub_opportunity(self, account_id, portal_url, error_message=""):
        """Create a stub opportunity for manual review when scraping fails"""
        stub_data = {
            'AccountId': account_id,
            'Name': f'Manual Review Required - {portal_url[:50]}',
            'StageName': 'Prospecting',
            'CloseDate': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
            'Response_Status__c': 'Scraper Error - Manual Review Needed',
            'Portal_URL__c': portal_url,
            'Data_Source__c': 'Automated Scraper',
            'Description': f'Scraper encountered an error. Manual review needed.\n\nError: {error_message}\n\nPortal URL: {portal_url}'
        }
        return self.create_salesforce_opportunity(stub_data)

    def map_solicitation_type(self, raw_type):
        """Map portal type to Salesforce picklist value"""
        if not raw_type:
            return 'Other'

        mapping = {
            'rfp': 'RFP - Request for Proposal',
            'rfb': 'RFB - Request for Bids',
            'rfq': 'RFQ - Request for Quote',
            'rfi': 'RFI - Request for Information',
            'ifb': 'IFB - Invitation for Bid',
            'rft': 'RFT - Request for Tender'
        }

        raw_lower = raw_type.lower()
        for key, value in mapping.items():
            if key in raw_lower:
                return value
        return 'Other'

    def map_category(self, raw_category):
        """Map portal category to Salesforce picklist value"""
        if not raw_category:
            return 'Other'

        mapping = {
            'legal': 'Legal Services',
            'construction': 'Construction',
            'equipment': 'Equipment',
            'technology': 'Technology/IT Services',
            'it services': 'Technology/IT Services',
            'professional': 'Professional Services',
            'consulting': 'Consulting',
            'supplies': 'Supplies',
            'maintenance': 'Maintenance/Repair',
            'healthcare': 'Healthcare',
            'medical': 'Healthcare'
        }

        raw_lower = raw_category.lower()
        for key, value in mapping.items():
            if key in raw_lower:
                return value
        return 'Other'

    def parse_closing_date(self, date_str):
        """Parse closing date string to YYYY-MM-DD format"""
        try:
            from dateutil import parser
            dt = parser.parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except:
            return None
