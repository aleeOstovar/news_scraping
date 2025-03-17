# News Scraper Application

A modular FastAPI application for scraping news articles from various sources, processing them, and sending them to an API.

## Features

- Scrape news articles from multiple sources
- Extract article content, images, and metadata
- Process and clean article data
- Upload images to an API
- Schedule scraping jobs
- RESTful API for manual control

## Architecture

The application follows a modular architecture:

- **Scrapers**: Site-specific scrapers that inherit from a base scraper class
- **Controller**: Manages scrapers and orchestrates the scraping process
- **API Client**: Handles communication with the backend API
- **Scheduler**: Manages scheduled scraping jobs
- **Models**: Pydantic models for data validation
- **Utils**: Helper functions for common tasks

## Project Structure

```
scraping/
├── app/
│   ├── controllers/
│   │   └── scraper_controller.py
│   ├── core/
│   │   ├── config.py
│   │   └── scheduler.py
│   ├── models/
│   │   └── article.py
│   ├── routers/
│   │   └── api.py
│   ├── scrapers/
│   │   ├── base_scraper.py
│   │   └── mihan_blockchain.py
│   ├── services/
│   │   └── api_client.py
│   ├── utils/
│   │   ├── date_utils.py
│   │   ├── image_utils.py
│   │   └── text_utils.py
│   └── main.py
├── .env
├── requirements.txt
└── run.py
```

## Setup

1. Clone the repository
2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a `.env` file based on the configuration in `app/core/config.py`
5. Run the application:
   ```
   python run.py
   ```

## Environment Variables

Create a `.env` file with the following variables:

```
# API Configuration
API_BASE_URL=http://your-api-url.com/api
API_KEY=your_api_key

# Scheduler Configuration
SCHEDULER_INTERVAL=3600  # Default interval in seconds
SCHEDULER_AUTO_START=true
SCHEDULER_TIMEZONE=UTC

# News Sources
ENABLED_SOURCES=mihan_blockchain

# User Agents
USER_AGENTS=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36,Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

## API Endpoints

- `GET /api/v1/status` - Get application status
- `POST /api/v1/scrape` - Trigger scraping for all enabled sources
- `POST /api/v1/scrape/{source_name}` - Trigger scraping for a specific source
- `GET /api/v1/scheduler/jobs` - Get scheduled jobs
- `POST /api/v1/scheduler/start` - Start the scheduler
- `POST /api/v1/scheduler/stop/{job_id}` - Stop a specific job

## Adding New Scrapers

1. Create a new file in `app/scrapers/` for your scraper
2. Inherit from the `BaseScraper` class
3. Implement the required methods
4. Add the scraper to the `ScraperController`

## Usage

### Command Line Arguments

The application supports several command line arguments:

```
python run.py --help
```

Options:
- `--host`: Host to run the API server on (default: 0.0.0.0)
- `--port`: Port to run the API server on (default: 8000)
- `--reload`: Enable auto-reload for development
- `--workers`: Number of worker processes (default: 1)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Running with Docker

A Dockerfile is provided to containerize the application:

```bash
# Build the Docker image
docker build -t news-scraper .

# Run the container
docker run -p 8000:8000 --env-file .env news-scraper
```

## License

MIT 