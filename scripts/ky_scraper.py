"""
Kentucky RFP Scraper for Salesforce Integration
Scrapes Kentucky eMars portal and returns JSON for Salesforce import
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import os
import requests
from datetime import datetime

# Environment variables
USERNAME = os.environ.get('KY_PORTAL_USERNAME')
PASSWORD = os.environ.get('KY_PORTAL_PASSWORD')
SF_API_KEY = os.environ.get('SALESFORCE_API_KEY')
SF_INSTANCE_URL = os.environ.get('SALESFORCE_INSTANCE_URL')

LOGIN_URL = "https://vss.ky.gov/vssprod-ext/Advantage4"

def setup_driver():
    """Setup headless Chrome driver for scraping"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    return webdriver.Chrome(options=chrome_options)

def login(driver, wait):
    """Login to Kentucky eMars portal"""
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD)
    wait.until(EC.element_to_be_clickable((By.ID, "loginButton"))).click()
    wait.until(EC.title_contains("Home Page"))
    print("✓ Logged in successfully")

def go_to_published_solicitations(driver, wait):
    """Navigate to Published Solicitations page"""
    wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Published Solicitations"))).click()
    wait.until(EC.title_contains("Published Solicitations"))
    print("✓ Navigated to Published Solicitations")

def sort_by_closing_date(driver):
    """Sort solicitations by closing date"""
    closing_col = driver.find_element(By.XPATH, "//th[contains(text(),'Closing Date and Time/Status')]")
    closing_col.click()
    time.sleep(2)
    print("✓ Sorted by closing date")

def get_solicitation_links(driver):
    """Extract all solicitation detail page links"""
    rows = driver.find_elements(By.XPATH, "//table//tr[td]")
    links = []
    for row in rows:
        try:
            link = row.find_element(By.XPATH, ".//a[contains(@href, 'Solicitation')]")
            links.append(link.get_attribute('href'))
        except:
            continue
    print(f"✓ Found {len(links)} solicitations")
    return links

def scrape_solicitation_detail(driver, wait, link):
    """Scrape individual solicitation details"""
    driver.get(link)
    time.sleep(2)

    data = {
        'portal_url': link,
        'scraped_at': datetime.utcnow().isoformat()
    }

    try:
        # General Info Tab
        data['solicitation_number'] = wait.until(
            EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'Solicitation Number')]/following-sibling::td"))
        ).text.strip()

        data['description'] = driver.find_element(By.XPATH, "//td[contains(text(),'Description')]/following-sibling::td").text.strip()
        data['buyer_name'] = driver.find_element(By.XPATH, "//td[contains(text(),'Buyer Name')]/following-sibling::td").text.strip()
        data['buyer_email'] = driver.find_element(By.XPATH, "//td[contains(text(),'Buyer Email')]/following-sibling::td").text.strip()
        data['buyer_phone'] = driver.find_element(By.XPATH, "//td[contains(text(),'Buyer Phone')]/following-sibling::td").text.strip()
        data['department'] = driver.find_element(By.XPATH, "//td[contains(text(),'Department')]/following-sibling::td").text.strip()
        data['closing_date'] = driver.find_element(By.XPATH, "//td[contains(text(),'Closing Date')]/following-sibling::td").text.strip()
        data['solicitation_type'] = driver.find_element(By.XPATH, "//td[contains(text(),'Type')]/following-sibling::td").text.strip()
        data['category'] = driver.find_element(By.XPATH, "//td[contains(text(),'Category')]/following-sibling::td").text.strip()

        # Attachments Tab
        try:
            attach_tab = driver.find_element(By.XPATH, "//a[contains(text(),'Attachments')]")
            attach_tab.click()
            time.sleep(1)

            attachments = []
            file_rows = driver.find_elements(By.XPATH, "//table[@id='attachmentsTable']//tr[td]")
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
        except Exception as e:
            data['attachments'] = []

    except Exception as e:
        print(f"✗ Error scraping {link}: {str(e)}")
        data['error'] = str(e)

    return data

def get_existing_solicitation_numbers():
    """Query Salesforce for existing solicitation numbers to avoid duplicates"""
    headers = {
        'Authorization': f'Bearer {SF_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Query for existing Kentucky opportunities
    query = "SELECT Solicitation_Number__c FROM Opportunity WHERE Account.Name = 'Commonwealth of Kentucky'"
    url = f"{SF_INSTANCE_URL}/services/data/v65.0/query/?q={query}"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        records = response.json().get('records', [])
        return {r['Solicitation_Number__c'] for r in records if r.get('Solicitation_Number__c')}
    return set()

def create_salesforce_opportunity(opportunity_data):
    """Create new opportunity in Salesforce via REST API"""
    headers = {
        'Authorization': f'Bearer {SF_API_KEY}',
        'Content-Type': 'application/json'
    }

    url = f"{SF_INSTANCE_URL}/services/data/v65.0/sobjects/Opportunity"

    response = requests.post(url, headers=headers, json=opportunity_data)
    if response.status_code == 201:
        return response.json()
    else:
        print(f"✗ Error creating opportunity: {response.text}")
        return None

def upload_attachment_to_salesforce(opportunity_id, file_name, file_url, driver):
    """Download attachment and upload to Salesforce as ContentVersion"""
    try:
        # Download file using Selenium (authenticated session)
        driver.get(file_url)
        time.sleep(2)

        # Get file content from download
        # Note: This requires proper download folder configuration
        # Alternative: Use requests with session cookies from Selenium

        headers = {
            'Authorization': f'Bearer {SF_API_KEY}',
            'Content-Type': 'application/json'
        }

        # Create ContentVersion (file)
        content_data = {
            'Title': file_name,
            'PathOnClient': file_name,
            'VersionData': '',  # Base64 encoded file content
            'FirstPublishLocationId': opportunity_id
        }

        url = f"{SF_INSTANCE_URL}/services/data/v65.0/sobjects/ContentVersion"
        response = requests.post(url, headers=headers, json=content_data)

        if response.status_code == 201:
            print(f"  ✓ Uploaded: {file_name}")
            return response.json()
        else:
            print(f"  ✗ Failed to upload {file_name}: {response.text}")
            return None

    except Exception as e:
        print(f"  ✗ Error uploading {file_name}: {str(e)}")
        return None

def main():
    """Main scraper execution"""
    print("Starting Kentucky RFP Scraper...")

    driver = setup_driver()
    wait = WebDriverWait(driver, 15)

    try:
        # Get existing solicitation numbers from Salesforce
        existing_numbers = get_existing_solicitation_numbers()
        print(f"Found {len(existing_numbers)} existing opportunities in Salesforce")

        # Login and navigate
        login(driver, wait)
        go_to_published_solicitations(driver, wait)
        sort_by_closing_date(driver)

        # Get all solicitation links
        links = get_solicitation_links(driver)

        new_opportunities = []

        # Scrape each solicitation
        for i, link in enumerate(links, 1):
            print(f"\n[{i}/{len(links)}] Scraping: {link}")
            data = scrape_solicitation_detail(driver, wait, link)

            # Skip if already exists in Salesforce
            if data.get('solicitation_number') in existing_numbers:
                print(f"  → Already exists, skipping")
                continue

            # Map to Salesforce Opportunity fields
            sf_opportunity = {
                'AccountId': '001V400000dOSjKIAW',  # Kentucky Account ID
                'Name': data.get('description', '')[:80],  # Truncate to 80 chars
                'Solicitation_Number__c': data.get('solicitation_number'),
                'Solicitation_Type__c': map_solicitation_type(data.get('solicitation_type')),
                'CloseDate': parse_closing_date(data.get('closing_date')),
                'StageName': 'Prospecting',
                'Department__c': data.get('department'),
                'Buyer_Name__c': data.get('buyer_name'),
                'Buyer_Email__c': data.get('buyer_email'),
                'Buyer_Phone__c': data.get('buyer_phone'),
                'RFP_Category__c': map_category(data.get('category')),
                'Response_Status__c': 'New - Not Reviewed',
                'Portal_URL__c': data.get('portal_url')
            }

            # Create opportunity in Salesforce
            result = create_salesforce_opportunity(sf_opportunity)

            if result:
                opp_id = result['id']
                print(f"  ✓ Created opportunity: {opp_id}")

                # Upload attachments
                if data.get('attachments'):
                    print(f"  Uploading {len(data['attachments'])} attachments...")
                    for attachment in data['attachments']:
                        upload_attachment_to_salesforce(
                            opp_id,
                            attachment['name'],
                            attachment['url'],
                            driver
                        )

                new_opportunities.append(data)

        print(f"\n{'='*60}")
        print(f"✓ Scrape complete!")
        print(f"  Total solicitations found: {len(links)}")
        print(f"  New opportunities created: {len(new_opportunities)}")
        print(f"{'='*60}")

        return {
            'success': True,
            'total_found': len(links),
            'new_created': len(new_opportunities),
            'opportunities': new_opportunities
        }

    except Exception as e:
        print(f"✗ Fatal error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        driver.quit()

def map_solicitation_type(raw_type):
    """Map portal type to Salesforce picklist value"""
    mapping = {
        'RFP': 'RFP - Request for Proposal',
        'RFB': 'RFB - Request for Bids',
        'RFQ': 'RFQ - Request for Quote',
        'RFI': 'RFI - Request for Information',
        'IFB': 'IFB - Invitation for Bid'
    }
    for key, value in mapping.items():
        if key.lower() in raw_type.lower():
            return value
    return 'Other'

def map_category(raw_category):
    """Map portal category to Salesforce picklist value"""
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

    if not raw_category:
        return 'Other'

    for key, value in mapping.items():
        if key in raw_category.lower():
            return value
    return 'Other'

def parse_closing_date(date_str):
    """Parse closing date string to YYYY-MM-DD format"""
    # Example: "10/14/2025 03:30 PM EDT" -> "2025-10-14"
    try:
        from dateutil import parser
        dt = parser.parse(date_str)
        return dt.strftime('%Y-%m-%d')
    except:
        return None

if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
