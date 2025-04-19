#!/usr/bin/env python
"""
Simple script to run the scraper directly for testing
"""
import logging
import sys
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run a specific news scraper")
parser.add_argument("scraper", type=str, nargs="?", default="mihan_blockchain", 
                    help="Name of the scraper to run (mihan_blockchain, arzdigital, defier)")
args = parser.parse_args()

# Configure logging to show detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import the scraper controller
from app.controllers.scraper_controller import ScraperController

# Create a controller instance
print("Creating ScraperController instance...")
controller = ScraperController()
print(f"Initialized ScraperController with {len(controller.scrapers)} scrapers")
print(f"Available scrapers: {list(controller.scrapers.keys())}")

# Validate the requested scraper
scraper_name = args.scraper
if scraper_name not in controller.scrapers:
    print(f"Error: Scraper '{scraper_name}' not found or not enabled.")
    print(f"Available scrapers: {list(controller.scrapers.keys())}")
    sys.exit(1)

# Run the selected scraper
print(f"\nRunning {scraper_name} scraper...")
results = controller.run_scraper(scraper_name)

# Print the results
print(f"\nScraper completed. Processed {len(results)} articles.")
for i, article in enumerate(results):
    print(f"Article {i+1}: {article.get('title')} - {article.get('sourceUrl')}")

print("\nDone!") 