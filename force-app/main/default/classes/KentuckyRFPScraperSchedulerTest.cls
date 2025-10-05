/**
 * Test class for KentuckyRFPScraperScheduler
 */
@isTest
private class KentuckyRFPScraperSchedulerTest {

    @isTest
    static void testScheduler() {
        // Set up mock HTTP response
        Test.setMock(HttpCalloutMock.class, new KentuckyScraperMock());

        Test.startTest();

        String cronExp = '0 0 6 * * ?';
        String jobId = System.schedule('Test Kentucky Scraper', cronExp, new KentuckyRFPScraperScheduler());

        // Verify job was scheduled
        System.assertNotEquals(null, jobId, 'Job should be scheduled');

        // Query scheduled job
        CronTrigger ct = [SELECT Id, CronExpression, TimesTriggered, NextFireTime
                          FROM CronTrigger WHERE Id = :jobId];

        System.assertEquals(cronExp, ct.CronExpression, 'Cron expression should match');
        System.assertEquals(0, ct.TimesTriggered, 'Job should not have run yet');

        Test.stopTest();
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
