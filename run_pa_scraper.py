#!/usr/bin/env python3
"""
Script to run Pennsylvania scraper on Heroku Scheduler
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from scrapers.pennsylvania import PennsylvaniaScraper

if __name__ == "__main__":
    print("="*80)
    print("PENNSYLVANIA eMARKETPLACE SCRAPER - Scheduled Run")
    print("="*80)

    scraper = PennsylvaniaScraper()
    scraper.scrape()

    print("\n" + "="*80)
    print("Pennsylvania scraper completed")
    print("="*80)
