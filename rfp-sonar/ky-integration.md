# **Kentucky VSS Scraper Specification**

## **Overview**

This document specifies the implementation of a new scraper for the **Kentucky Vendor Self Service (VSS)** portal. The goal is to automate the manual workflow of logging in, filtering for open opportunities, and syncing them to Salesforce as Opportunity records.

This implementation must align with the existing RFP Sonar architecture defined in ARCHITECTURE.md, specifically inheriting from BaseScraper.

## **Target System Details**

* **Jurisdiction:** Kentucky  
* **Portal URL:** https://vss.ky.gov/  
* **Technology:** CGI Advantage Vendor Self Service (VSS) 4.0  
* **Authentication:** Required (User ID \+ Password)  
* **Browser Engine:** Playwright (Chromium)

## **Workflow Analysis (from Video)**

1. **Login:** User enters User ID/Password on home page.  
2. **Dashboard:** User lands on a dashboard and clicks the "Published Solicitations" tile/tab.  
3. **Search/Filter:** \* User sees a search form.  
   * User selects "Open" from the "Status" dropdown.  
   * User clicks "Search".  
4. **Results:** A table loads with columns for Description, Department, Solicitation Number, and Closing Date.  
5. **Extraction:** We need to extract these fields for every row and deduplicate against Salesforce.

## **implementation Guide**

### **1\. Environment Variables (Heroku Config)**

The scraper requires credentials to access the portal. These should be stored in Heroku config vars, not hardcoded.

heroku config:set KY\_VSS\_USERNAME="\<actual\_username\>"  
heroku config:set KY\_VSS\_PASSWORD="\<actual\_password\>"

### **2\. Class Structure**

Create a new file: scrapers/kentucky.py.

**Key Requirements:**

* Inherit from BaseScraper.  
* Set self.jurisdiction\_code \= 'KY' (Must match Salesforce Account Record).  
* Use sync\_playwright for browser automation.  
* Implement scrape() method.

### **3\. The Code (scrapers/kentucky.py)**

from .base\_scraper import BaseScraper  
from playwright.sync\_api import sync\_playwright  
import os  
import re  
from datetime import datetime

class KentuckyScraper(BaseScraper):  
    def \_\_init\_\_(self):  
        super().\_\_init\_\_()  
        self.jurisdiction\_code \= 'KY' \# Matches Salesforce Account Billing\_State\_Code\_\_c  
        self.portal\_url \= '\[https://vss.ky.gov/\](https://vss.ky.gov/)'  
          
        \# Load Credentials  
        self.vss\_user \= os.environ.get('KY\_VSS\_USERNAME')  
        self.vss\_pass \= os.environ.get('KY\_VSS\_PASSWORD')  
          
        \# Get Account ID from Salesforce  
        self.account\_id \= self.get\_account\_id()

    def parse\_date(self, date\_str):  
        """  
        Parses VSS date format: "10/14/2025 03:30 PM EDT"  
        Returns YYYY-MM-DD string  
        """  
        try:  
            if not date\_str:  
                return None  
            \# Remove timezone/extra text if present (e.g. " EDT")  
            clean\_date \= date\_str.split(' ')\[0\]   
            return datetime.strptime(clean\_date, '%m/%d/%Y').strftime('%Y-%m-%d')  
        except Exception as e:  
            print(f"  Date parse error for '{date\_str}': {e}")  
            return None

    def scrape(self):  
        print(f"Starting Kentucky VSS Scrape for Account: {self.account\_id}")  
          
        if not self.vss\_user or not self.vss\_pass:  
            raise ValueError("Missing KY\_VSS\_USERNAME or KY\_VSS\_PASSWORD environment variables.")

        try:  
            \# 1\. Deduplication: Get existing Solicitation Numbers from Salesforce  
            existing\_numbers \= self.get\_existing\_solicitation\_numbers(self.account\_id)  
            print(f"Found {len(existing\_numbers)} existing solicitations in Salesforce.")

            with sync\_playwright() as p:  
                \# Launch Headless Chrome  
                browser \= p.chromium.launch(headless=True)  
                \# Set User Agent to avoid basic bot detection  
                context \= browser.new\_context(user\_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  
                page \= context.new\_page()

                \# \--- STEP 1: LOGIN \---  
                print("Navigating to VSS Login...")  
                page.goto(self.portal\_url)  
                  
                \# Fill Login Form (Using Labels for robustness)  
                print(f"Logging in as {self.vss\_user}...")  
                page.get\_by\_label("User ID").fill(self.vss\_user)  
                page.get\_by\_label("Password").fill(self.vss\_pass)  
                page.get\_by\_role("button", name="Sign In").click()  
                  
                \# Wait for Dashboard to load (look for specific text or element)  
                page.wait\_for\_load\_state("networkidle")  
                  
                \# \--- STEP 2: NAVIGATE TO PUBLISHED SOLICITATIONS \---  
                print("Navigating to Published Solicitations...")  
                \# Click the large tab/icon shown in video  
                page.get\_by\_role("link", name="Published Solicitations").click()  
                  
                \# \--- STEP 3: SEARCH & FILTER \---  
                print("Filtering for OPEN solicitations...")  
                  
                \# Wait for the Search Grid/Form to be visible  
                page.wait\_for\_selector("table", state="visible", timeout=30000)  
                  
                \# Interact with Status Dropdown  
                \# The video shows a dropdown labeled "Status". We select "Open".  
                \# Note: If label selector fails, fallback to name="Status" or similar.  
                status\_dropdown \= page.locator("select\[name\*='Status'\]")  
                  
                if status\_dropdown.is\_visible():  
                    status\_dropdown.select\_option(label="Open")  
                      
                    \# Click Search  
                    page.get\_by\_role("button", name="Search").click()  
                      
                    \# Wait for table refresh  
                    page.wait\_for\_load\_state("networkidle")  
                    page.wait\_for\_timeout(3000) \# Grace period for JS table render  
                  
                \# \--- STEP 4: EXTRACT DATA \---  
                \# Select all rows in the results table.   
                \# Video shows standard HTML table structure.  
                rows \= page.locator("table\[summary='Search Results'\] \> tbody \> tr").all()  
                print(f"Found {len(rows)} rows in search results.")

                new\_opps\_count \= 0

                for row in rows:  
                    try:  
                        cells \= row.locator("td").all()  
                        \# Ensure row has enough columns (skipping headers/empty rows)  
                        if len(cells) \< 5:  
                            continue

                        \# Column Mapping (Based on Video):  
                        \# Col 1 (Index 1): Description / Title  
                        \# Col 2 (Index 2): Department  
                        \# Col 3 (Index 3): Solicitation Number (e.g., "RFB-758-2500000223-1")  
                        \# Col 4 (Index 4): Closing Date  
                          
                        description\_raw \= cells\[1\].inner\_text().strip()  
                        solicitation\_raw \= cells\[3\].inner\_text().strip()  
                        date\_raw \= cells\[4\].inner\_text().strip()  
                          
                        \# Clean Solicitation ID (remove newlines if any)  
                        solicitation\_number \= solicitation\_raw.split('\\n')\[0\].strip()

                        \# Deduplication: Skip if exists  
                        if solicitation\_number in existing\_numbers:  
                            \# print(f"Skipping existing: {solicitation\_number}")  
                            continue

                        \# Get Link (Essential for Phase 2: Attachments)  
                        link\_element \= row.locator("a").first  
                        if link\_element.count() \> 0:  
                            link\_href \= link\_element.get\_attribute("href")  
                            full\_link \= f"\[https://vss.ky.gov\](https://vss.ky.gov){link\_href}" if link\_href and link\_href.startswith("/") else link\_href  
                        else:  
                            full\_link \= self.portal\_url

                        \# Parse Date  
                        close\_date \= self.parse\_date(date\_raw)  
                        if not close\_date:  
                            close\_date \= (datetime.now()).strftime('%Y-%m-%d') \# Fallback to today if parsing fails

                        \# Construct Salesforce Opportunity Data  
                        opp\_data \= {  
                            'Name': description\_raw\[:120\], \# SF Limit 120 chars  
                            'AccountId': self.account\_id,  
                            'Solicitation\_Number\_\_c': solicitation\_number,  
                            'CloseDate': close\_date,  
                            'StageName': 'Prospecting',  
                            'Description': (  
                                f"Full Title: {description\_raw}\\n"  
                                f"Solicitation ID: {solicitation\_raw}\\n"  
                                f"Link: {full\_link}\\n"  
                                f"Extracted Date: {date\_raw}"  
                            )  
                        }

                        \# Create in Salesforce  
                        self.create\_salesforce\_opportunity(opp\_data)  
                        new\_opps\_count \+= 1  
                        print(f"✓ Created: {solicitation\_number}")

                    except Exception as row\_error:  
                        print(f"Error parsing row: {str(row\_error)}")  
                        continue

                browser.close()

            \# 5\. Success  
            self.update\_account\_scrape\_status(self.account\_id, 'Success')  
            print(f"Scrape Complete. Created {new\_opps\_count} new opportunities.")

        except Exception as e:  
            \# 6\. Failure  
            print(f"CRITICAL FAILURE: {str(e)}")  
            self.update\_account\_scrape\_status(self.account\_id, 'Failed', str(e))  
            raise

### **4\. Integration Step**

Add the new scraper to the main execution loop in run\_all\_scrapers.py:

\# run\_all\_scrapers.py

\# ... existing imports ...  
from scrapers.kentucky import KentuckyScraper

scrapers \= \[  
    \# ... existing scrapers ...  
    ('Kentucky', KentuckyScraper()),  
\]

### **5\. Future Phase (Attachments)**

Note for future implementation:  
To download attachments, the script will need to be updated to:

1. Click row.locator("a").first.click() to open the detail view.  
2. Wait for the "Attachments" tab to appear.  
3. Click the "Attachments" tab.  
4. Iterate through the attachment links and use page.expect\_download() to save files.  
5. Use page.go\_back() to return to the list.