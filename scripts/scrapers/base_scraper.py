"""
Base scraper class that all jurisdiction scrapers inherit from
"""
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import os
import requests
from datetime import datetime


class BaseScraper(ABC):
    """Abstract base class for all procurement portal scrapers"""

    def __init__(self):
        self.driver = None
        self.wait = None
        self.sf_api_key = os.environ.get('SALESFORCE_API_KEY')
        self.sf_instance_url = os.environ.get('SALESFORCE_INSTANCE_URL')

    def setup_driver(self):
        """Setup headless Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # Use new headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--single-process')  # Required for Heroku
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Set Chrome binary location if on Heroku
        chrome_bin = os.environ.get('GOOGLE_CHROME_BIN')
        if not chrome_bin:
            # Try to find Chrome in typical Heroku paths
            possible_paths = [
                '/app/.chrome-for-testing/chrome-linux64/chrome',
                '/app/.apt/usr/bin/google-chrome',
                '/usr/bin/google-chrome'
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    chrome_bin = path
                    break

        if chrome_bin:
            chrome_options.binary_location = chrome_bin

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)
        return self.driver, self.wait

    def cleanup(self):
        """Close browser and cleanup"""
        if self.driver:
            self.driver.quit()

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
