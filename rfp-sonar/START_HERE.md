# 🔍 Kentucky Scraper - Next Session Prompt

## Copy this to start a new session with Claude:

```
I'm debugging the Kentucky VSS scraper. Please run this command to open a visible browser and show me what's happening:

cd /Users/yves/Developer/rfpsonar-salesforce/rfp-sonar && export KY_VSS_USERNAME="rfpsonar" && export KY_VSS_PASSWORD="fYrqyb-8nyrfo" && python3 debug_local_headed.py

The scraper currently:
✅ Logs in successfully
✅ Clicks "Published Solicitations" button
✅ Handles disclaimer modal (clicks "I Agree")
❌ Finds 0 rows in results table

After running the script, please tell me:
1. What is the URL after clicking "I Agree"?
2. What tables are visible on the page?
3. Is there a search form or filters we need to interact with?
4. Do you see any solicitations listed on the page?
```

## Quick Reference

**Project Location:** `/Users/yves/Developer/rfpsonar-salesforce/rfp-sonar`

**Main Files:**
- `scrapers/kentucky.py` - Main scraper (currently deployed to Heroku)
- `debug_local_headed.py` - Local debug script with visible browser
- `RUN_LOCAL_DEBUG.md` - Instructions for running locally

**Current Status:**
- ✅ Login works
- ✅ Dashboard navigation works
- ✅ "Published Solicitations" button click works (with force click)
- ✅ Disclaimer modal handling works
- ❌ Finding 0 rows in table (need to debug what's on page after disclaimer)

**Heroku App:** `rfpsonar-scraper-72c03056271a.herokuapp.com`

**Test Endpoint:** `curl https://rfpsonar-scraper-72c03056271a.herokuapp.com/scrape/kentucky`

**View Logs:** `heroku logs --tail --app rfpsonar-scraper`
