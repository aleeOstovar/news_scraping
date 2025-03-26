#!/usr/bin/env python
"""
Simple script to run the scraper directly for testing
"""
import logging
import sys

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

# Check the processed URLs loaded
print(f"Number of processed URLs loaded: {len(controller._processed_urls)}")
print(f"First 5 processed URLs (if any): {list(controller._processed_urls)[:5] if controller._processed_urls else []}")

# Run the scraper
print("\nRunning mihan_blockchain scraper...")
results = controller.run_scraper('mihan_blockchain')

# Print the results
print(f"\nScraper completed. Processed {len(results)} articles.")
for i, article in enumerate(results):
    print(f"Article {i+1}: {article.get('title')} - {article.get('sourceUrl')}")

print("\nDone!") 