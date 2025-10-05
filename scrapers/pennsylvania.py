"""
Pennsylvania eMARKETPLACE Scraper
Scrapes https://www.emarketplace.state.pa.us/
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import time
import os
import csv
from datetime import datetime
from .base_scraper import BaseScraper


class PennsylvaniaScraper(BaseScraper):
    """Scraper for Pennsylvania eMARKETPLACE procurement portal"""

    def __init__(self):
        super().__init__()
        self.base_url = "https://www.emarketplace.state.pa.us/Search.aspx"
        self.account_id = '001V400000dOSjfIAG'  # Commonwealth of Pennsylvania

    def get_account_id(self):
        """Return Pennsylvania Account ID"""
        return self.account_id

    def navigate_to_solicitations(self):
        """Navigate to search page and set to show ALL records"""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state('networkidle')
        time.sleep(2)

        try:
            # Select "ALL" from the records per page dropdown
            # First, find the dropdown - it's typically a select element
            self.page.select_option('select[name*="ddlRecordsPerPage"]', 'ALL')
            time.sleep(2)
            print("✓ Pennsylvania: Set to show ALL records per page")
        except Exception as e:
            print(f"✗ Pennsylvania: Failed to select ALL records: {str(e)}")
            # Continue anyway - default might be sufficient

    def export_csv(self):
        """Click export button and download CSV"""
        try:
            # Set up download listener before clicking
            with self.page.expect_download() as download_info:
                # Click the Export Search Results button
                self.page.click('text=Export Search Results')
                download = download_info.value

            # Save the downloaded file
            download_path = '/tmp/pa_solicitations.csv'
            download.save_as(download_path)
            print(f"✓ Pennsylvania: Downloaded CSV to {download_path}")
            return download_path

        except Exception as e:
            print(f"✗ Pennsylvania: Failed to export CSV: {str(e)}")
            raise

    def parse_csv(self, csv_path):
        """Parse the downloaded CSV and extract solicitation data"""
        solicitations = []

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Actual CSV columns: Bid No, Bid Type, Title, Description, Agency, County,
                # Bid Start Date, Bid End Date, Bid Open Date, Status, Buyer Name, Updated Date
                bid_no = row.get('Bid No', '').strip()
                title = row.get('Title', '').strip()
                description = row.get('Description', '').strip()

                # Combine title and description for opportunity name/description
                full_description = f"{title}\n\n{description}" if title and description else (title or description)

                solicitation = {
                    'solicitation_number': bid_no,
                    'title': title,
                    'description': full_description,
                    'department': row.get('Agency', '').strip(),
                    'bid_start_date': row.get('Bid Start Date', '').strip(),
                    'bid_end_date': row.get('Bid End Date', '').strip(),
                    'bid_open_date': row.get('Bid Open Date', '').strip(),
                    'status': row.get('Status', '').strip(),
                    'portal_url': f"https://www.emarketplace.state.pa.us/Solicitations.aspx?SID={bid_no}" if bid_no else '',
                    'solicitation_type': row.get('Bid Type', '').strip(),
                    'buyer_name': row.get('Buyer Name', '').strip(),
                    'county': row.get('County', '').strip(),
                }

                solicitations.append(solicitation)

        print(f"✓ Pennsylvania: Parsed {len(solicitations)} solicitations from CSV")
        return solicitations

    def parse_date(self, date_str):
        """Parse Pennsylvania date format to Salesforce format"""
        if not date_str:
            return None

        try:
            # Try common date formats
            for fmt in ['%m/%d/%Y', '%m/%d/%Y %I:%M:%S %p', '%Y-%m-%d', '%m/%d/%y']:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

            print(f"⚠ Pennsylvania: Could not parse date: {date_str}")
            return None

        except Exception as e:
            print(f"✗ Pennsylvania: Date parsing error: {str(e)}")
            return None

    def create_opportunity(self, data):
        """Create Salesforce opportunity from solicitation data"""
        # Use title as Name (truncated to 80 chars)
        title = data.get('title', '')
        if not title:
            title = data.get('solicitation_number', 'Untitled')

        # Map to Salesforce fields using existing fields where possible
        sf_opp = {
            'AccountId': self.get_account_id(),
            'Name': title[:80],  # Truncate to 80 chars
            'Solicitation_Number__c': data.get('solicitation_number'),
            'Solicitation_Type__c': self.map_solicitation_type(data.get('solicitation_type')),
            'CloseDate': self.parse_date(data.get('bid_end_date')) or self.get_default_close_date(),
            'StageName': 'Prospecting',
            'Department__c': data.get('department'),
            'Buyer_Name__c': data.get('buyer_name'),
            'Response_Status__c': 'New - Not Reviewed',
            'Portal_URL__c': data.get('portal_url'),
            'Data_Source__c': 'Automated Scraper',
            'Description': data.get('description', ''),
        }

        return self.create_salesforce_opportunity(sf_opp)

    def scrape(self):
        """Main scraping workflow"""
        print(f"\n{'='*60}")
        print(f"Pennsylvania eMARKETPLACE Scraper")
        print(f"{'='*60}\n")

        self.setup_browser()

        try:
            # Navigate and prepare the page
            self.navigate_to_solicitations()

            # Export the CSV
            csv_path = self.export_csv()

            # Parse the CSV
            solicitations = self.parse_csv(csv_path)

            # Get existing solicitations to avoid duplicates
            existing_sols = self.get_existing_solicitations(self.get_account_id())

            # Create opportunities
            created_count = 0
            skipped_count = 0
            error_count = 0

            for sol in solicitations:
                try:
                    sol_num = sol.get('solicitation_number')

                    # Skip if already exists
                    if sol_num in existing_sols:
                        skipped_count += 1
                        continue

                    result = self.create_opportunity(sol)
                    if result:
                        created_count += 1
                        print(f"✓ Created: {sol_num}")
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"✗ Error creating opportunity for {sol.get('solicitation_number')}: {str(e)}")
                    error_count += 1

            print(f"\n{'='*60}")
            print(f"Pennsylvania Scrape Complete!")
            print(f"  Created: {created_count}")
            print(f"  Skipped (already exist): {skipped_count}")
            print(f"  Errors: {error_count}")
            print(f"{'='*60}\n")

            # Clean up CSV file
            if os.path.exists(csv_path):
                os.remove(csv_path)

        except Exception as e:
            print(f"\n✗ Pennsylvania scraper failed: {str(e)}")
            import traceback
            traceback.print_exc()

            # Create stub opportunity for manual review
            self.create_stub_opportunity(
                self.get_account_id(),
                self.base_url,
                str(e)
            )

        finally:
            self.close_browser()


if __name__ == "__main__":
    scraper = PennsylvaniaScraper()
    scraper.scrape()
