# Deploying News Scraper to Production

This guide provides step-by-step instructions for deploying the News Scraper application to a production environment, such as a VPS or cloud hosting service.

## Prerequisites

- A VPS or cloud server running Ubuntu 20.04 or newer (Digital Ocean, AWS, Linode, etc.)
- SSH access to your server
- A domain name (optional, but recommended)
- Basic knowledge of Linux commands

## 1. Server Setup

### 1.1 Update Server Packages

Connect to your server via SSH and update the system:

```bash
ssh user@your-server-ip
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Required Packages

Install Python and required tools:

```bash
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor
```

## 2. Application Deployment

### 2.1 Create Application Directory

Create a directory for the application:

```bash
mkdir -p /opt/news-scraper
```

### 2.2 Clone the Repository

Clone the repository to your server:

```bash
cd /opt/news-scraper
git clone https://github.com/yourusername/news-scraper.git .
# Or upload your files using SCP/SFTP if not using git
```

### 2.3 Create Virtual Environment

Set up a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2.4 Install Dependencies

Install the required packages:

```bash
pip install -r requirements.txt
```

## 3. Configuration

### 3.1 Set Up Environment Variables

Copy the example environment file and edit it:

```bash
cp .env.example .env
nano .env
```

Update the following configuration:

- `API_BASE_URL`: The URL of your API
- `API_KEY`: Your API key
- `ENABLED_SOURCES`: Comma-separated list of enabled sources (mihan_blockchain,arzdigital,defier)
- `DB_URL`: Your database connection string

### 3.2 Configure Supervisor

Create a supervisor configuration:

```bash
sudo nano /etc/supervisor/conf.d/news-scraper.conf
```

Add the following content:

```ini
[program:news-scraper]
directory=/opt/news-scraper
command=/opt/news-scraper/venv/bin/python run.py
autostart=true
autorestart=true
stderr_logfile=/var/log/news-scraper.err.log
stdout_logfile=/var/log/news-scraper.out.log
user=root
environment=PYTHONPATH="/opt/news-scraper"
```

Update supervisor to apply the new configuration:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start news-scraper
```

## 4. Manual Execution (Alternative to Supervisor)

If you prefer to run the application manually or using cron:

### 4.1 Running the Application

```bash
cd /opt/news-scraper
source venv/bin/activate
python run.py
```

### 4.2 Setting Up Cron Jobs

For periodic execution without the built-in scheduler:

```bash
crontab -e
```

Add a line to run the scraper every 2 hours:

```cron
0 */2 * * * cd /opt/news-scraper && source venv/bin/activate && python run_scraper.py
```

## 5. Using Docker (Optional)

If you prefer using Docker for deployment:

### 5.1 Install Docker

```bash
sudo apt install -y docker.io docker-compose
```

### 5.2 Build Docker Image

```bash
cd /opt/news-scraper
docker build -t news-scraper .
```

### 5.3 Run with Docker

First, create a docker-compose.yml file:

```bash
nano docker-compose.yml
```

Add the following content:

```yaml
version: '3'
services:
  news-scraper:
    image: news-scraper
    restart: always
    volumes:
      - ./logs:/app/logs
    env_file:
      - .env
```

Start the container:

```bash
docker-compose up -d
```

## 6. Monitoring and Maintenance

### 6.1 Checking Logs

To check application logs:

```bash
# If using Supervisor
sudo tail -f /var/log/news-scraper.out.log
sudo tail -f /var/log/news-scraper.err.log

# If using Docker
docker-compose logs -f
```

### 6.2 Updating the Application

To update the application:

```bash
cd /opt/news-scraper
git pull  # If using git

# Restart the application
sudo supervisorctl restart news-scraper
# Or if using Docker
docker-compose restart
```

### 6.3 Troubleshooting

If the application fails to start:

1. Check log files for errors
2. Verify all dependencies are installed
3. Confirm environment variables are correct
4. Ensure the database connection is working
5. Test the API connection

## 7. Security Considerations

1. Use a non-root user for running the application
2. Implement proper firewall rules
3. Set up regular updates
4. Use HTTPS for API connections
5. Store sensitive credentials securely

## 8. Performance Optimization

For high-volume scraping:

1. Increase server resources (CPU/RAM)
2. Implement caching mechanisms
3. Consider distributed scraping (multiple servers)
4. Optimize database queries
5. Implement rate limiting to avoid overloading sources

## Additional Resources

- [Supervisor Documentation](http://supervisord.org/)
- [Docker Documentation](https://docs.docker.com/)
- [Nginx Configuration Guide](https://www.nginx.com/resources/wiki/start/)
- [Cron Job Guide](https://help.ubuntu.com/community/CronHowto) 