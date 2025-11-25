"""
Salesforce OAuth authentication helper
Handles access token refresh using OAuth refresh tokens
"""
import os
import requests
from datetime import datetime, timedelta


class SalesforceAuth:
    """Manages Salesforce OAuth authentication with automatic token refresh"""

    def __init__(self):
        self.instance_url = os.environ.get('SF_INSTANCE_URL')
        self.consumer_key = os.environ.get('SF_CONSUMER_KEY')
        self.consumer_secret = os.environ.get('SF_CONSUMER_SECRET')
        self.refresh_token = os.environ.get('SF_REFRESH_TOKEN')

        # Legacy support for direct API key (will be deprecated)
        self.legacy_api_key = os.environ.get('SALESFORCE_API_KEY')

        self.access_token = None
        self.token_expires_at = None

        if not all([self.instance_url, self.consumer_key, self.consumer_secret, self.refresh_token]):
            if not self.legacy_api_key:
                raise ValueError(
                    "Missing Salesforce OAuth credentials. Required: "
                    "SF_INSTANCE_URL, SF_CONSUMER_KEY, SF_CONSUMER_SECRET, SF_REFRESH_TOKEN"
                )
            print("⚠️  WARNING: Using legacy SALESFORCE_API_KEY. Please migrate to OAuth refresh tokens.")

    def get_access_token(self):
        """Get a valid access token, refreshing if necessary"""

        # If using legacy API key, return it
        if self.legacy_api_key and not self.refresh_token:
            return self.legacy_api_key

        # If we have a valid token, return it
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token

        # Otherwise, refresh the token
        return self._refresh_access_token()

    def _refresh_access_token(self):
        """Exchange refresh token for a new access token"""
        token_url = "https://login.salesforce.com/services/oauth2/token"

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.consumer_key,
            'client_secret': self.consumer_secret,
            'refresh_token': self.refresh_token
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']

            # Tokens typically expire in 2 hours, but we'll refresh after 1.5 hours to be safe
            self.token_expires_at = datetime.now() + timedelta(hours=1, minutes=30)

            print(f"✓ Successfully refreshed Salesforce access token (expires in ~1.5 hours)")

            return self.access_token

        except requests.exceptions.RequestException as e:
            print(f"✗ Error refreshing Salesforce access token: {e}")
            if hasattr(e.response, 'text'):
                print(f"  Response: {e.response.text}")
            raise
