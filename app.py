"""
Multi-Tenant RFP Scraper API
Supports scrapers for states, counties, cities via dynamic routes
"""
from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Simple API key authentication
API_KEY = os.environ.get('API_KEY', 'your-secret-api-key')

# Import scrapers
from scrapers.kentucky import KentuckyScraper
from scrapers.massachusetts import MassachusettsScraper
from scrapers.pennsylvania import PennsylvaniaScraper
# from scrapers.california import CaliforniaScraper  # Future
# from scrapers.texas import TexasScraper  # Future
# from scrapers.jefferson_county_ky import JeffersonCountyKYScraper  # Future

# Scraper registry - maps route names to scraper classes
SCRAPERS = {
    'kentucky': KentuckyScraper,
    'massachusetts': MassachusettsScraper,
    'pennsylvania': PennsylvaniaScraper,
    # 'california': CaliforniaScraper,
    # 'texas': TexasScraper,
    # 'jefferson-county-ky': JeffersonCountyKYScraper,
}


def verify_api_key():
    """Check API key in request headers"""
    if request.headers.get('X-API-Key') != API_KEY:
        return False
    return True


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'scrapers_available': list(SCRAPERS.keys())
    }), 200


@app.route('/scrapers', methods=['GET'])
def list_scrapers():
    """List all available scrapers"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    return jsonify({
        'scrapers': list(SCRAPERS.keys()),
        'count': len(SCRAPERS)
    }), 200


@app.route('/scrape/<jurisdiction>', methods=['POST'])
def scrape(jurisdiction):
    """
    Trigger scrape for a specific jurisdiction

    Examples:
      POST /scrape/kentucky
      POST /scrape/california
      POST /scrape/jefferson-county-ky

    Headers:
      X-API-Key: your-secret-api-key
    """
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    # Check if scraper exists
    if jurisdiction not in SCRAPERS:
        return jsonify({
            'error': f'Scraper not found: {jurisdiction}',
            'available_scrapers': list(SCRAPERS.keys())
        }), 404

    try:
        # Instantiate and run scraper
        scraper_class = SCRAPERS[jurisdiction]
        scraper = scraper_class()
        result = scraper.scrape()

        return jsonify({
            'jurisdiction': jurisdiction,
            **result
        }), 200

    except Exception as e:
        return jsonify({
            'jurisdiction': jurisdiction,
            'error': str(e)
        }), 500


@app.route('/scrape/batch', methods=['POST'])
def scrape_batch():
    """
    Trigger scrapes for multiple jurisdictions

    Body:
      {
        "jurisdictions": ["kentucky", "california", "texas"]
      }

    Headers:
      X-API-Key: your-secret-api-key
    """
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        jurisdictions = data.get('jurisdictions', [])

        if not jurisdictions:
            return jsonify({'error': 'No jurisdictions specified'}), 400

        results = {}

        for jurisdiction in jurisdictions:
            if jurisdiction not in SCRAPERS:
                results[jurisdiction] = {
                    'success': False,
                    'error': f'Scraper not found: {jurisdiction}'
                }
                continue

            try:
                scraper_class = SCRAPERS[jurisdiction]
                scraper = scraper_class()
                result = scraper.scrape()
                results[jurisdiction] = result
            except Exception as e:
                results[jurisdiction] = {
                    'success': False,
                    'error': str(e)
                }

        # Calculate totals
        total_new = sum(r.get('new_created', 0) for r in results.values() if r.get('success'))
        total_found = sum(r.get('total_found', 0) for r in results.values() if r.get('success'))

        return jsonify({
            'batch': True,
            'jurisdictions_processed': len(results),
            'total_new_created': total_new,
            'total_found': total_found,
            'results': results
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
