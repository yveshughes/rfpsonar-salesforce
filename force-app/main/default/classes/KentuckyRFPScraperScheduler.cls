/**
 * Schedulable class to trigger Kentucky RFP scraper daily
 * Schedule: Every day at 6:00 AM
 */
public class KentuckyRFPScraperScheduler implements Schedulable {

    public void execute(SchedulableContext ctx) {
        // Call future method to perform HTTP callout
        KentuckyRFPScraperCallout.triggerScraper();
    }

    /**
     * Schedule this job to run daily at 6:00 AM
     * Run this in Anonymous Apex or via Setup UI:
     *
     * KentuckyRFPScraperScheduler scheduler = new KentuckyRFPScraperScheduler();
     * String cronExp = '0 0 6 * * ?'; // Daily at 6:00 AM
     * System.schedule('Kentucky RFP Daily Scraper', cronExp, scheduler);
     */
}
