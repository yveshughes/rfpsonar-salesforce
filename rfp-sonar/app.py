"""
Simple Flask app for Heroku deployment
This app exists only to satisfy Heroku's web dyno requirement
The actual scrapers run via Heroku Scheduler
"""
from flask import Flask, jsonify
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return 'RFP Sonar Scraper - Running on Heroku'

@app.route('/health')
def health():
    return {'status': 'healthy'}

@app.route('/scrape/kentucky')
def scrape_kentucky():
    """Manually trigger Kentucky scraper"""
    def run_scraper():
        try:
            from scrapers.kentucky import KentuckyScraper
            scraper = KentuckyScraper()
            scraper.scrape()
            print("✓ Kentucky scraper completed successfully")
        except Exception as e:
            print(f"✗ Kentucky scraper failed: {str(e)}")
            import traceback
            traceback.print_exc()

    # Run in background thread so request returns immediately
    thread = threading.Thread(target=run_scraper)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': 'Kentucky scraper started in background'})

@app.route('/scrape/pennsylvania')
def scrape_pennsylvania():
    """Manually trigger Pennsylvania scraper"""
    def run_scraper():
        try:
            from scrapers.pennsylvania import PennsylvaniaScraper
            scraper = PennsylvaniaScraper()
            scraper.scrape()
            print("✓ Pennsylvania scraper completed successfully")
        except Exception as e:
            print(f"✗ Pennsylvania scraper failed: {str(e)}")
            import traceback
            traceback.print_exc()

    # Run in background thread so request returns immediately
    thread = threading.Thread(target=run_scraper)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': 'Pennsylvania scraper started in background'})

@app.route('/test/kentucky')
def test_kentucky():
    """Test Kentucky login functionality"""
    def run_test():
        try:
            import subprocess
            result = subprocess.run(['python', 'test_ky_login.py'],
                                  capture_output=True,
                                  text=True,
                                  timeout=120)
            print("=== TEST STDOUT ===")
            print(result.stdout)
            print("=== TEST STDERR ===")
            print(result.stderr)
            print(f"=== EXIT CODE: {result.returncode} ===")
        except Exception as e:
            print(f"✗ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()

    # Run in background thread
    thread = threading.Thread(target=run_test)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': 'Kentucky login test started - check logs'})

if __name__ == '__main__':
    app.run()
