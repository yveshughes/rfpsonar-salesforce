# Kentucky Scraper - Local Debug

## Quick Start Command

Copy and paste this command to run the scraper locally with a **visible browser**:

```bash
cd /Users/yves/Developer/rfpsonar-salesforce/rfp-sonar && export KY_VSS_USERNAME="rfpsonar" && export KY_VSS_PASSWORD="fYrqyb-8nyrfo" && python3 debug_local_headed.py
```

## What This Does

1. Opens a **visible Chromium browser window**
2. Navigates to Kentucky VSS portal
3. Logs in automatically
4. Clicks "Published Solicitations" button
5. Handles the disclaimer modal (clicks "I Agree")
6. Shows you exactly what's on the page after each step
7. **Pauses with browser open** so you can inspect the page
8. Takes a screenshot at `/tmp/ky_local_debug.png`

## How to Use

1. Run the command above in your terminal
2. Watch the browser window as it performs each step
3. When you see the message "Press Enter to continue...", the browser will stay open
4. You can now inspect the page, look at the DevTools, etc.
5. Press Enter in the terminal to close the browser

## Troubleshooting

If you get an error about Playwright not being installed:

```bash
pip3 install playwright
playwright install chromium
```

## What to Look For

After the scraper clicks "I Agree", check:
- What is the current URL?
- Is there a table on the page?
- Is there a search form or filters visible?
- Do you see any solicitations/opportunities listed?
