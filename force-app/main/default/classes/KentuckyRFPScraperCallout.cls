/**
 * Apex class to call external Kentucky RFP scraper
 * Scheduled to run daily to check for new opportunities
 */
public with sharing class KentuckyRFPScraperCallout {

    // Heroku endpoint URL (configure in Custom Metadata or Custom Setting)
    private static final String SCRAPER_ENDPOINT = 'https://your-heroku-app.herokuapp.com/scrape/kentucky';

    /**
     * Main method to trigger scraper via HTTP callout
     */
    @future(callout=true)
    public static void triggerScraper() {
        try {
            HttpRequest req = new HttpRequest();
            req.setEndpoint(SCRAPER_ENDPOINT);
            req.setMethod('POST');
            req.setHeader('Content-Type', 'application/json');
            req.setHeader('X-API-Key', getAPIKey());
            req.setTimeout(120000); // 2 minute timeout

            Http http = new Http();
            HttpResponse res = http.send(req);

            if (res.getStatusCode() == 200) {
                Map<String, Object> result = (Map<String, Object>) JSON.deserializeUntyped(res.getBody());

                System.debug('Scraper Result: ' + result);

                Integer newOpps = (Integer) result.get('new_created');
                Integer totalFound = (Integer) result.get('total_found');

                // Log successful scrape
                logScraperRun(true, newOpps, totalFound, null);

            } else {
                System.debug('Error: ' + res.getStatus() + ' - ' + res.getBody());
                logScraperRun(false, 0, 0, res.getStatus() + ': ' + res.getBody());
            }

        } catch (Exception e) {
            System.debug('Exception: ' + e.getMessage());
            logScraperRun(false, 0, 0, e.getMessage());
        }
    }

    /**
     * Get API key from Named Credential or Custom Setting
     */
    private static String getAPIKey() {
        // Option 1: Store in Custom Metadata
        // Scraper_Config__mdt config = Scraper_Config__mdt.getInstance('Kentucky');
        // return config.API_Key__c;

        // Option 2: Hardcode for now (NOT RECOMMENDED for production)
        return 'your-secret-api-key';
    }

    /**
     * Log scraper run for monitoring
     */
    private static void logScraperRun(Boolean success, Integer newOpps, Integer totalFound, String errorMsg) {
        // Create a custom object to track scraper runs
        // Or use Platform Events for real-time monitoring

        System.debug('=== Scraper Run Log ===');
        System.debug('Success: ' + success);
        System.debug('New Opportunities: ' + newOpps);
        System.debug('Total Found: ' + totalFound);
        if (!success) {
            System.debug('Error: ' + errorMsg);
        }
        System.debug('=======================');
    }
}
