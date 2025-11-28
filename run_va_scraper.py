#!/usr/bin/env python3
"""
Run Virginia scraper
Usage: python3 run_va_scraper.py
"""
import sys
import os

# Add parent directory to path to allow package imports
sys.path.insert(0, os.path.dirname(__file__))

from scrapers.virginia import VirginiaScraper

if __name__ == "__main__":
    print("Starting Virginia scraper...")
    scraper = VirginiaScraper()
    try:
        result = scraper.scrape()
        print(f"\nResult: {result}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
