# Multi-Tenant RFP Scraper

## Architecture

One Heroku app serves **all jurisdictions** (states, counties, cities) via dynamic routes:

```
POST /scrape/kentucky
POST /scrape/california
POST /scrape/jefferson-county-ky
POST /scrape/louisville-ky
POST /scrape/batch  (multiple jurisdictions at once)
```

### Benefits

✅ **Cost Effective**: $7/month for ALL scrapers (vs $7 per scraper)
✅ **Easy to Add**: Just create a new scraper class and register it
✅ **Shared Code**: All scrapers inherit from `BaseScraper`
✅ **Batch Processing**: Scrape multiple jurisdictions in one call
✅ **Centralized Monitoring**: One set of logs, one app to monitor

## Project Structure

```
scripts/
├── app.py                    # Flask API with dynamic routes
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py      # Base class all scrapers inherit from
│   ├── kentucky.py          # Kentucky eMars scraper
│   ├── california.py        # California (future)
│   ├── texas.py             # Texas (future)
│   └── jefferson_county_ky.py  # County-level (future)
├── requirements.txt
├── Procfile
└── runtime.txt
```

## Adding a New Scraper

### 1. Create Scraper Class

```python
# scrapers/california.py
from .base_scraper import BaseScraper
from selenium.webdriver.common.by import By

class CaliforniaScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.account_id = '001XXXXXXXXXX'  # CA Account ID
        self.portal_url = "https://caleprocure.ca.gov"

    def get_account_id(self):
        return self.account_id

    def scrape(self):
        self.setup_driver()
        try:
            # Your scraping logic here
            self.driver.get(self.portal_url)
            # ... scrape solicitations
            # ... create opportunities
            return {'success': True, 'new_created': 10, 'total_found': 50}
        finally:
            self.cleanup()
```

### 2. Register in app.py

```python
# app.py
from scrapers.california import CaliforniaScraper

SCRAPERS = {
    'kentucky': KentuckyScraper,
    'california': CaliforniaScraper,  # <-- Add this
}
```

### 3. Deploy

```bash
git add .
git commit -m "Add California scraper"
git push heroku main
```

### 4. Test

```bash
curl -X POST https://your-app.herokuapp.com/scrape/california \
  -H "X-API-Key: your-secret-key"
```

That's it! No new Heroku app needed.

## API Endpoints

### GET /health
Check if app is running
```bash
curl https://your-app.herokuapp.com/health
```

Response:
```json
{
  "status": "healthy",
  "scrapers_available": ["kentucky", "california"]
}
```

### GET /scrapers
List all available scrapers (requires API key)
```bash
curl https://your-app.herokuapp.com/scrapers \
  -H "X-API-Key: your-secret-key"
```

### POST /scrape/{jurisdiction}
Scrape a single jurisdiction
```bash
curl -X POST https://your-app.herokuapp.com/scrape/kentucky \
  -H "X-API-Key: your-secret-key"
```

Response:
```json
{
  "jurisdiction": "kentucky",
  "success": true,
  "total_found": 44,
  "new_created": 5,
  "opportunities": [...]
}
```

### POST /scrape/batch
Scrape multiple jurisdictions in one request
```bash
curl -X POST https://your-app.herokuapp.com/scrape/batch \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdictions": ["kentucky", "california", "texas"]
  }'
```

Response:
```json
{
  "batch": true,
  "jurisdictions_processed": 3,
  "total_new_created": 25,
  "total_found": 150,
  "results": {
    "kentucky": {"success": true, "new_created": 5, ...},
    "california": {"success": true, "new_created": 12, ...},
    "texas": {"success": true, "new_created": 8, ...}
  }
}
```

## Salesforce Integration

### Single Jurisdiction (Scheduled)

```apex
// KentuckyRFPScraperCallout.cls
private static final String SCRAPER_ENDPOINT = 'https://your-app.herokuapp.com/scrape/kentucky';
```

### Multi-Jurisdiction (Batch)

```apex
// BatchScraperCallout.cls
private static final String SCRAPER_ENDPOINT = 'https://your-app.herokuapp.com/scrape/batch';

public static void triggerBatchScraper() {
    HttpRequest req = new HttpRequest();
    req.setEndpoint(SCRAPER_ENDPOINT);
    req.setMethod('POST');
    req.setHeader('X-API-Key', getAPIKey());
    req.setHeader('Content-Type', 'application/json');

    Map<String, Object> body = new Map<String, Object>{
        'jurisdictions' => new List<String>{'kentucky', 'california', 'texas'}
    };
    req.setBody(JSON.serialize(body));

    Http http = new Http();
    HttpResponse res = http.send(req);
    // ... handle response
}
```

## Environment Variables

```bash
# Heroku config
heroku config:set SALESFORCE_API_KEY="your_sf_token"
heroku config:set SALESFORCE_INSTANCE_URL="https://yourorg.my.salesforce.com"
heroku config:set API_KEY="your-secret-api-key"

# Jurisdiction-specific credentials
heroku config:set KY_PORTAL_USERNAME="ky_user"
heroku config:set KY_PORTAL_PASSWORD="ky_pass"
heroku config:set CA_PORTAL_USERNAME="ca_user"
heroku config:set CA_PORTAL_PASSWORD="ca_pass"
```

## Deployment

```bash
cd scripts/

# Create app (ONCE)
heroku create rfpsonar-scraper

# Add buildpacks (ONCE)
heroku buildpacks:add heroku/python
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-chromedriver

# Set env vars (ONCE)
heroku config:set API_KEY="choose-secure-key"
heroku config:set SALESFORCE_API_KEY="your_token"
heroku config:set SALESFORCE_INSTANCE_URL="https://ndmm.my.salesforce.com"

# Deploy (EVERY TIME you update code)
git init
git add .
git commit -m "Update scrapers"
git push heroku main
```

## Monitoring

```bash
# View logs
heroku logs --tail --app rfpsonar-scraper

# Check status
heroku ps --app rfpsonar-scraper

# Scale up for more performance
heroku ps:scale web=1:standard-1x --app rfpsonar-scraper
```

## Cost Breakdown

### Single App (Multi-Tenant)
- **Hobby Dyno**: $7/month
- **Standard Dyno**: $25/month (no sleep, better performance)
- Supports **unlimited** scrapers

### vs. Separate Apps
- **50 states × $7 = $350/month** 😱
- **Counties/cities = $$$$$** 😱😱😱

## Future Enhancements

1. **Async Background Jobs**: Use Celery + Redis for long-running scrapes
2. **Rate Limiting**: Prevent abuse with `flask-limiter`
3. **Webhook Notifications**: POST results back to Salesforce when done
4. **Scraper Status Dashboard**: Web UI to monitor all scrapers
5. **Auto-Discovery**: Scrape portal lists to find new jurisdictions
6. **Smart Scheduling**: Scrape based on portal update frequency
