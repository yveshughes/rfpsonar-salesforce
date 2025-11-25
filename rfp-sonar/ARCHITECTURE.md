# RFP Sonar - System Architecture Overview

## High-Level Overview

RFP Sonar is an automated system that scrapes government procurement portals for RFP (Request for Proposal) opportunities and stores them in Salesforce. The system runs on Heroku with daily scheduled jobs.

## Architecture Components

### 1. Salesforce (Data Storage & UI)
- **Objects:**
  - `Account` (Government Agency record type) - Stores information about each government jurisdiction
  - `Opportunity` - Stores individual RFP/solicitation records

- **Key Account Fields:**
  - `Name` - Government agency name (e.g., "Commonwealth of Kentucky")
  - `Procurement_Portal_URL__c` - URL to the procurement portal
  - `Portal_Username__c` - Login credentials for portal
  - `Portal_Password__c` - Login credentials for portal
  - `Last_Scrape_Date__c` - Timestamp of last successful scrape
  - `Scraper_Status__c` - Picklist: "Not Configured", "Success", "Failed", "Running"
  - `Billing_State_Code__c` - State abbreviation (e.g., "KY", "PA")

- **Key Opportunity Fields:**
  - `Name` - RFP title/description
  - `AccountId` - Link to Government Agency Account
  - `Solicitation_Number__c` - Unique identifier from portal (used for deduplication)
  - `CloseDate` - RFP due date/closing date
  - `Amount` - Contract value (if available)
  - `Description` - RFP description/details
  - `StageName` - Always set to "Prospecting"

### 2. Heroku Application (Scraper Runtime)
- **Platform:** Heroku with Python buildpack
- **Deployment:** Git subtree push from `rfp-sonar/` subdirectory
- **Scheduling:** Heroku Scheduler addon runs scrapers daily

- **Key Files:**
  - `Procfile` - Defines web dyno: `web: gunicorn app:app`
  - `requirements.txt` - Python dependencies (playwright, requests, flask, gunicorn)
  - `Aptfile` - System dependencies for Playwright browsers
  - `.profile` - Environment setup script for Playwright
  - `app.py` - Minimal Flask app (required for web dyno, actual scrapers run via scheduler)

### 3. Python Scraper Architecture

#### Base Components

**`scrapers/salesforce_auth.py`** - OAuth Authentication Handler
```python
class SalesforceAuth:
    def __init__(self):
        # Loads credentials from environment variables
        # SF_INSTANCE_URL, SF_CONSUMER_KEY, SF_CONSUMER_SECRET, SF_REFRESH_TOKEN

    def get_access_token(self):
        # Returns cached access token or refreshes if expired
        # Tokens cached for 90 minutes
```

**`scrapers/base_scraper.py`** - Base Class for All Scrapers
```python
class BaseScraper:
    def __init__(self):
        # Initialize Salesforce OAuth
        self.sf_auth = SalesforceAuth()
        self.sf_instance_url = self.sf_auth.instance_url

    def get_account_id(self):
        # Queries Salesforce for Account ID by state code
        # Override jurisdiction_code in child class

    def get_existing_solicitation_numbers(self, account_id):
        # Queries Salesforce for existing Solicitation_Number__c values
        # Returns set of strings for deduplication
        # Prevents creating duplicate Opportunities

    def create_salesforce_opportunity(self, opp_data):
        # Creates new Opportunity in Salesforce via REST API
        # Required fields: Name, AccountId, Solicitation_Number__c,
        #                  CloseDate, StageName

    def update_account_scrape_status(self, account_id, status, error_message=None):
        # Updates Account's Last_Scrape_Date__c and Scraper_Status__c
        # status must be exact picklist value: "Success", "Failed", "Running"
        # Called at end of scrape() - success or failure

    def scrape(self):
        # Must be implemented by child class
        raise NotImplementedError()
```

#### Jurisdiction-Specific Scrapers

**Pattern for Creating New Scraper:**

```python
from .base_scraper import BaseScraper
from playwright.sync_api import sync_playwright
import re
from datetime import datetime

class KentuckyScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.jurisdiction_code = 'KY'  # Must match Account.Billing_State_Code__c
        self.portal_url = 'https://portal-url.gov'
        self.account_id = self.get_account_id()

    def scrape(self):
        try:
            # 1. Get existing solicitation numbers to avoid duplicates
            existing_numbers = self.get_existing_solicitation_numbers(self.account_id)

            # 2. Launch Playwright browser
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 3. Navigate and scrape
                page.goto(self.portal_url)
                # ... scraping logic ...

                # 4. For each RFP found:
                for rfp in rfps:
                    solicitation_number = extract_solicitation_number(rfp)

                    # Skip if already exists
                    if solicitation_number in existing_numbers:
                        continue

                    # Extract data
                    opp_data = {
                        'Name': extract_title(rfp),
                        'AccountId': self.account_id,
                        'Solicitation_Number__c': solicitation_number,
                        'CloseDate': parse_date(rfp),  # YYYY-MM-DD format
                        'StageName': 'Prospecting',
                        'Description': extract_description(rfp)
                    }

                    # Create in Salesforce
                    self.create_salesforce_opportunity(opp_data)
                    print(f"✓ Created: {opp_data['Name']}")

                browser.close()

            # 5. Update scrape status to Success
            self.update_account_scrape_status(self.account_id, 'Success')

        except Exception as e:
            # 6. Update scrape status to Failed
            self.update_account_scrape_status(self.account_id, 'Failed', str(e))
            raise
```

**Existing Scrapers:**

1. **`scrapers/kentucky.py`** - Kentucky eMars Portal
   - Uses Playwright for browser automation
   - Handles pagination
   - Extracts: title, solicitation number, due date, description

2. **`scrapers/pennsylvania.py`** - Pennsylvania eMARKETPLACE
   - Uses Playwright for browser automation
   - Searches for opportunities from last 30 days
   - Handles date parsing errors gracefully

### 4. Orchestration

**`run_all_scrapers.py`** - Main Entry Point
```python
# Imports all scraper classes
from scrapers.kentucky import KentuckyScraper
from scrapers.pennsylvania import PennsylvaniaScraper

# List of scrapers to run
scrapers = [
    ('Kentucky', KentuckyScraper()),
    ('Pennsylvania', PennsylvaniaScraper()),
]

# Run each scraper, catch exceptions, report results
for name, scraper in scrapers:
    try:
        scraper.scrape()
        results[name] = "SUCCESS"
    except Exception as e:
        results[name] = f"FAILED: {str(e)}"
```

**Heroku Scheduler Configuration:**
- Command: `python run_all_scrapers.py`
- Frequency: Daily (recommended: early morning)

## Data Flow

```
1. Heroku Scheduler triggers run_all_scrapers.py
                    ↓
2. For each jurisdiction:
   a. Initialize scraper (loads credentials, queries Account ID)
   b. Query existing Solicitation_Number__c values from Salesforce
   c. Launch Playwright browser
   d. Navigate to procurement portal
   e. Extract RFP data (title, number, date, description)
   f. For each new RFP:
      - Skip if Solicitation_Number__c already exists
      - Create Opportunity in Salesforce via REST API
   g. Close browser
   h. Update Account.Last_Scrape_Date__c and Scraper_Status__c
                    ↓
3. Print summary report (successes/failures)
```

## Authentication & Security

### Salesforce OAuth Flow
1. **One-time Setup:**
   - Create Connected App in Salesforce with OAuth scopes
   - Run `get_refresh_token.py` locally to obtain refresh token
   - Store credentials in Heroku config vars

2. **Runtime Authentication:**
   - `SalesforceAuth` class uses refresh token to get access tokens
   - Access tokens cached for 90 minutes
   - Automatic refresh when expired
   - No username/password storage needed

### Environment Variables (Heroku Config)
```bash
SF_INSTANCE_URL=https://yourorg.my.salesforce.com
SF_CONSUMER_KEY=<Connected App Consumer Key>
SF_CONSUMER_SECRET=<Connected App Consumer Secret>
SF_REFRESH_TOKEN=<OAuth Refresh Token>
```

## Browser Automation (Playwright)

### Why Playwright?
- Many procurement portals use JavaScript-heavy SPAs
- Handles dynamic content, AJAX requests, pagination
- Can interact with forms, buttons, dropdowns
- Supports headless mode for server environments

### Heroku Configuration for Playwright
- **Aptfile** installs system dependencies (libnss3, libatk1.0-0, etc.)
- **.profile** runs `playwright install` on dyno startup
- Chromium browser downloaded to `/app/.cache/ms-playwright/`

## Deduplication Strategy

**Critical:** Each scraper must check existing solicitation numbers before creating Opportunities.

```python
# At start of scrape():
existing_numbers = self.get_existing_solicitation_numbers(self.account_id)

# For each RFP found:
if solicitation_number in existing_numbers:
    print(f"  Skipping existing: {solicitation_number}")
    continue
```

This prevents duplicate Opportunities when:
- Scraper runs multiple times per day
- Portal returns same RFPs across multiple days
- Manual re-runs during testing

## Error Handling & Monitoring

### Status Tracking
- `Scraper_Status__c` field shows health of each scraper
- "Success" = Last run completed without errors
- "Failed" = Exception occurred during scrape
- View in Salesforce "Government Agencies" list view

### Error Scenarios
1. **Portal login fails** → Update status to "Failed", log error
2. **Invalid date format** → Skip individual RFP, continue scraping
3. **Salesforce API error** → Fail entire scrape, update status
4. **Browser timeout** → Fail scrape, update status

### Logging
- Print statements go to Heroku logs: `heroku logs --tail`
- Each created Opportunity logged: "✓ Created: RFP Title"
- Errors include stack traces for debugging

## Deployment Workflow

### Initial Setup
1. Create Heroku app: `heroku create rfpsonar-scraper`
2. Add buildpacks: `heroku-community/apt`, `heroku/python`
3. Set config vars: `heroku config:set SF_INSTANCE_URL=...`
4. Create Heroku Scheduler addon

### Deploying Updates
```bash
# From repository root
cd rfpsonar-salesforce

# Deploy only rfp-sonar subdirectory to Heroku
git push heroku $(git subtree split --prefix rfp-sonar main):main --force
```

### Adding New Scraper
1. Create `scrapers/new_jurisdiction.py` using pattern above
2. Add jurisdiction to `run_all_scrapers.py`:
   ```python
   from scrapers.new_jurisdiction import NewJurisdictionScraper
   scrapers.append(('New Jurisdiction', NewJurisdictionScraper()))
   ```
3. Ensure Account exists in Salesforce with correct `Billing_State_Code__c`
4. Commit and deploy to Heroku

## Testing

### Local Testing
```bash
# Set environment variables
export SF_INSTANCE_URL="https://yourorg.my.salesforce.com"
export SF_CONSUMER_KEY="..."
export SF_CONSUMER_SECRET="..."
export SF_REFRESH_TOKEN="..."

# Run individual scraper
python -c "from scrapers.kentucky import KentuckyScraper; KentuckyScraper().scrape()"

# Run all scrapers
python run_all_scrapers.py
```

### Heroku Testing
```bash
# One-off dyno execution
heroku run python run_all_scrapers.py --app rfpsonar-scraper

# View logs
heroku logs --tail --app rfpsonar-scraper
```

## Common Patterns & Best Practices

### Date Parsing
```python
from datetime import datetime
import re

# Clean and parse dates
date_str = "11/25/2025 3:00 PM EST"
try:
    close_date = datetime.strptime(date_str, '%m/%d/%Y %I:%M %p %Z').strftime('%Y-%m-%d')
except:
    print(f"  Invalid date: {date_str}, skipping")
    continue
```

### Solicitation Number Extraction
```python
# Extract from text
text = "Solicitation #: RFP-2025-001234"
match = re.search(r'RFP-\d{4}-\d+', text)
solicitation_number = match.group(0) if match else None

# Validate
if not solicitation_number:
    print(f"  No solicitation number found, skipping")
    continue
```

### Pagination
```python
while True:
    # Scrape current page
    rfps = page.query_selector_all('.rfp-row')
    for rfp in rfps:
        # Process RFP
        pass

    # Check for next page
    next_button = page.query_selector('a.next-page')
    if not next_button or next_button.is_disabled():
        break

    next_button.click()
    page.wait_for_load_state('networkidle')
```

### Handling Dynamic Content
```python
# Wait for element to appear
page.wait_for_selector('.rfp-list', timeout=30000)

# Wait for network to be idle
page.wait_for_load_state('networkidle')

# Wait for specific text
page.wait_for_function("() => document.body.innerText.includes('Search Results')")
```

## Salesforce Configuration

### Account Record Type Setup
- Record Type: "Government Agency"
- Picklist values must be assigned to record type for `Scraper_Status__c`
- Each jurisdiction needs one Account record with correct `Billing_State_Code__c`

### Connected App Setup
1. Setup → App Manager → New Connected App
2. Enable OAuth Settings
3. Callback URL: `http://localhost:8080/callback`
4. Selected OAuth Scopes: `Full access (full)`, `Perform requests at any time (refresh_token)`, `Access and manage data (api)`
5. Save and retrieve Consumer Key/Secret

## Troubleshooting

### "bad value for restricted picklist field"
- Picklist values not activated or not assigned to record type
- Go to Setup → Object Manager → Account → Record Types → Government Agency
- Edit Scraper Status picklist, move values from Available to Selected

### "INVALID_SESSION_ID" errors
- Refresh token expired or invalid
- Re-run `get_refresh_token.py` to obtain new token
- Update Heroku config: `heroku config:set SF_REFRESH_TOKEN=...`

### Browser fails to launch on Heroku
- Check Aptfile has all required system dependencies
- Verify .profile runs `playwright install`
- Check logs for "Failed to install browser dependencies"

### Duplicate Opportunities created
- Ensure `get_existing_solicitation_numbers()` called at start
- Verify deduplication check before creating each Opportunity
- Check if `Solicitation_Number__c` is being extracted correctly

## Future Enhancements

### Potential Features
- Email notifications on scraper failures
- Dashboard showing scrape history and trends
- Automatic retry logic for transient errors
- Support for scrapers requiring login credentials
- Webhook integration for real-time alerts
- AI-powered RFP categorization and matching
- Multi-page detail scraping for full RFP documents

### Additional Jurisdictions
To add more states, follow the scraper pattern and ensure:
1. Account record exists in Salesforce
2. Scraper class implements deduplication
3. Error handling updates status field
4. Added to `run_all_scrapers.py` orchestration
