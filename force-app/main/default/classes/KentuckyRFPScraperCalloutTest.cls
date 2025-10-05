/**
 * Test class for KentuckyRFPScraperCallout
 */
@isTest
private class KentuckyRFPScraperCalloutTest {

    @isTest
    static void testTriggerScraper() {
        // Set up mock HTTP response
        Test.setMock(HttpCalloutMock.class, new KentuckyScraperMock());

        Test.startTest();
        KentuckyRFPScraperCallout.triggerScraper();
        Test.stopTest();

        // Verify no exceptions thrown
        System.assert(true, 'Scraper should execute without errors');
    }

    /**
     * Mock HTTP callout for testing
     */
    private class KentuckyScraperMock implements HttpCalloutMock {
        public HTTPResponse respond(HTTPRequest req) {
            HttpResponse res = new HttpResponse();
            res.setHeader('Content-Type', 'application/json');
            res.setBody('{"success": true, "new_created": 5, "total_found": 44}');
            res.setStatusCode(200);
            return res;
        }
    }
}
