# Kentucky RFP Automated Scraper

## Overview

This system automatically scrapes the Kentucky eMars procurement portal daily and creates new Opportunity records in Salesforce, including attachments.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Salesforce    │      │  Heroku Python   │      │  Kentucky       │
│   Scheduled     │─────>│  Scraper API     │─────>│  eMars Portal   │
│   Apex Job      │      │  (Selenium)      │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
         │                        │
         │<───────────────────────┘
         │       Create Opportunities
         │       + Upload Attachments
```

## Setup Instructions

### 1. Deploy Python Scraper to Heroku

```bash
cd scripts/

# Login to Heroku
heroku login

# Create new Heroku app
heroku create rfpsonar-ky-scraper

# Add buildpacks for Chrome/Selenium
heroku buildpacks:add --index 1 heroku/python
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 3 https://github.com/heroku/heroku-buildpack-chromedriver

# Set environment variables
heroku config:set KY_PORTAL_USERNAME="your_username"
heroku config:set KY_PORTAL_PASSWORD="your_password"
heroku config:set SALESFORCE_API_KEY="your_salesforce_session_id_or_oauth_token"
heroku config:set SALESFORCE_INSTANCE_URL="https://ndmm.my.salesforce.com"
heroku config:set API_KEY="your-secret-api-key"

# Deploy to Heroku
git init
git add .
git commit -m "Initial scraper deployment"
heroku git:remote -a rfpsonar-ky-scraper
git push heroku main

# Test the endpoint
curl -X POST https://rfpsonar-ky-scraper.herokuapp.com/health
```

### 2. Configure Salesforce Remote Site Settings

1. Go to **Setup → Security → Remote Site Settings**
2. Click **New Remote Site**
3. Name: `Heroku_Scraper`
4. Remote Site URL: `https://rfpsonar-ky-scraper.herokuapp.com`
5. Click **Save**

### 3. Deploy Apex Classes to Salesforce

```bash
cd ..

# Deploy Apex classes
sf project deploy start --source-dir force-app/main/default/classes/Kentucky*.cls* --target-org ndmm
```

### 4. Schedule the Daily Job

Open **Developer Console** → **Debug** → **Open Execute Anonymous Window** and run:

```apex
KentuckyRFPScraperScheduler scheduler = new KentuckyRFPScraperScheduler();
String cronExp = '0 0 6 * * ?'; // Daily at 6:00 AM
System.schedule('Kentucky RFP Daily Scraper', cronExp, scheduler);
```

Or via Setup UI:
1. **Setup → Apex Classes → Schedule Apex**
2. Job Name: `Kentucky RFP Daily Scraper`
3. Apex Class: `KentuckyRFPScraperScheduler`
4. Frequency: Daily
5. Start Time: 6:00 AM
6. Click **Save**

### 5. Test Manually

Run this in Anonymous Apex:

```apex
KentuckyRFPScraperCallout.triggerScraper();
```

Check Debug Logs for results.

## How It Works

1. **Salesforce Scheduled Job** runs daily at 6:00 AM
2. **Apex makes HTTP POST** to Heroku scraper endpoint
3. **Python scraper**:
   - Logs into Kentucky eMars portal
   - Navigates to Published Solicitations
   - Scrapes all RFP/RFB details
   - Queries Salesforce for existing `Solicitation_Number__c` values
   - Skips duplicates
   - Creates new Opportunities via Salesforce REST API
   - Downloads and uploads PDF attachments to Salesforce
4. **Returns JSON** with count of new opportunities created

## Attachment Handling

The scraper:
1. Identifies attachments on each solicitation detail page
2. Downloads PDF files using authenticated Selenium session
3. Converts to Base64
4. Uploads as `ContentVersion` linked to the Opportunity
5. Files appear in the **Files** related list on each Opportunity

## Monitoring

### View Scheduled Jobs
Setup → Scheduled Jobs → Find "Kentucky RFP Daily Scraper"

### View Debug Logs
Setup → Debug Logs → Filter by "KentuckyRFPScraperCallout"

### Check Heroku Logs
```bash
heroku logs --tail --app rfpsonar-ky-scraper
```

## Troubleshooting

### Scraper Returns 401 Unauthorized
- Check that `X-API-Key` header matches Heroku `API_KEY` config
- Update `getAPIKey()` method in `KentuckyRFPScraperCallout.cls`

### Scraper Times Out
- Increase timeout in Apex: `req.setTimeout(120000);` (max 120 seconds)
- Optimize scraper to process fewer pages per run
- Split into multiple smaller jobs

### Portal Login Fails
- Verify `KY_PORTAL_USERNAME` and `KY_PORTAL_PASSWORD` in Heroku config
- Check if portal changed login selectors (update `ky_scraper.py`)

### Attachments Not Uploading
- Ensure Selenium download folder is configured
- Check file size limits (Salesforce max: 2GB per ContentVersion)
- Verify `SALESFORCE_API_KEY` has ContentVersion create permissions

## Security Notes

- **API Keys**: Store in Custom Metadata, not hardcoded
- **Portal Credentials**: Use Heroku Config Vars (encrypted)
- **Salesforce Token**: Use OAuth2 with refresh token, not session ID
- **Heroku Dyno**: Use Private Spaces for sensitive data

## Cost Estimates

### Heroku
- **Hobby Dyno**: $7/month (sleeps after 30 min inactivity)
- **Standard Dyno**: $25/month (no sleep)
- **Buildpacks**: Free
- **Data Transfer**: Minimal (~1GB/month)

### Salesforce
- **API Calls**: ~50-100 per day (well within limits)
- **Storage**: ~10MB per day for attachments (monitor limits)

## Future Enhancements

1. **Error Notifications**: Send email/Slack on scraper failures
2. **Scraper Logs Object**: Track all runs in Salesforce custom object
3. **Multiple States**: Extend to scrape all 50 states
4. **AI Categorization**: Use OpenAI to auto-categorize RFPs
5. **Bid/No-Bid Scoring**: ML model to recommend opportunities
