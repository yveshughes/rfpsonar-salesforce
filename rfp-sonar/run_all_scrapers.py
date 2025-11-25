#!/usr/bin/env python3
"""
Script to run all jurisdiction scrapers on Heroku Scheduler
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from scrapers.kentucky import KentuckyScraper
from scrapers.pennsylvania import PennsylvaniaScraper

if __name__ == "__main__":
    print("="*80)
    print("RFP SONAR - DAILY SCRAPER RUN")
    print("="*80)

    scrapers = [
        ('Kentucky', KentuckyScraper()),
        ('Pennsylvania', PennsylvaniaScraper()),
    ]

    results = {}

    for name, scraper in scrapers:
        print(f"\n{'='*80}")
        print(f"Running {name} Scraper...")
        print(f"{'='*80}\n")

        try:
            scraper.scrape()
            results[name] = "SUCCESS"
        except Exception as e:
            print(f"\n✗ {name} scraper failed: {str(e)}")
            import traceback
            traceback.print_exc()
            results[name] = f"FAILED: {str(e)}"

    print(f"\n{'='*80}")
    print("DAILY SCRAPER RUN - SUMMARY")
    print(f"{'='*80}")
    for jurisdiction, status in results.items():
        print(f"  {jurisdiction}: {status}")
    print(f"{'='*80}\n")
