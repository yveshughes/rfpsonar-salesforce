#!/usr/bin/env python3
"""
Check if Pennsylvania scraper has run
"""
import requests
import os

# Get from environment (set by Heroku)
api_key = os.environ.get('SALESFORCE_API_KEY')
instance_url = os.environ.get('SALESFORCE_INSTANCE_URL')

if not api_key or not instance_url:
    print("Error: SALESFORCE_API_KEY and SALESFORCE_INSTANCE_URL must be set")
    print("\nRun this on Heroku instead:")
    print("  heroku run python3 check_pa_status.py")
    exit(1)

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

# Query for Pennsylvania opportunities
query = "SELECT COUNT() FROM Opportunity WHERE AccountId = '001V400000dOSjfIAG'"

import urllib.parse
encoded_query = urllib.parse.quote(query)
url = f"{instance_url}/services/data/v65.0/query/?q={encoded_query}"

response = requests.get(url, headers=headers)

if response.status_code == 200:
    count = response.json().get('totalSize', 0)

    print("="*70)
    print("PENNSYLVANIA SCRAPER STATUS CHECK")
    print("="*70)
    print(f"\nPennsylvania Opportunities: {count}")

    if count > 0:
        print("\n✅ SCRAPER HAS RUN SUCCESSFULLY!")
        print(f"   {count} opportunities have been created")

        # Get sample records
        query2 = """
        SELECT Name, Solicitation_Number__c, Data_Source__c, CreatedDate
        FROM Opportunity
        WHERE AccountId = '001V400000dOSjfIAG'
        ORDER BY CreatedDate DESC
        LIMIT 3
        """
        encoded_query2 = urllib.parse.quote(query2)
        url2 = f"{instance_url}/services/data/v65.0/query/?q={encoded_query2}"
        response2 = requests.get(url2, headers=headers)

        if response2.status_code == 200:
            records = response2.json().get('records', [])
            print("\n   Sample opportunities:")
            for r in records:
                print(f"   • {r['Solicitation_Number__c']}: {r['Name'][:50]}")
    else:
        print("\n⏳ SCRAPER HAS NOT RUN YET")
        print("   The scraper is either still running or hasn't started")
        print("\n   To check Heroku logs:")
        print("     heroku logs --tail --app rfpsonar-scraper")

    print("\n" + "="*70 + "\n")
else:
    print(f"Error querying Salesforce: {response.text}")
