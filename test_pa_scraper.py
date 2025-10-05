#!/usr/bin/env python3
"""
Test script for Pennsylvania scraper
"""
import os
import sys

# Add scrapers directory to path
sys.path.insert(0, os.path.dirname(__file__))

from scrapers.pennsylvania import PennsylvaniaScraper

if __name__ == "__main__":
    print("Testing Pennsylvania Scraper...")
    print("="*60)

    scraper = PennsylvaniaScraper()
    scraper.scrape()
