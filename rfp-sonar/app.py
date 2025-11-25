"""
Simple Flask app for Heroku deployment
This app exists only to satisfy Heroku's web dyno requirement
The actual scrapers run via Heroku Scheduler
"""
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return 'RFP Sonar Scraper - Running on Heroku'

@app.route('/health')
def health():
    return {'status': 'healthy'}

if __name__ == '__main__':
    app.run()
