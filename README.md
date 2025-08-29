# ⚽ 3. Liga Table of Justice

> **Expected Goals (xG) and Expected Points (xP) analytics dashboard for German 3. Liga**

A repo  that scrapes match data, calculates Expected Goals (xG) and Expected Points (xP), and presents the results in an interactive dashboard.

## Features

- **Data Collection**: Automated scraping from FootyStats and Soccerway
- **Advanced Analytics**: xG-based Expected Points calculations using Poisson distribution  
- **Interactive Dashboard**: Modern Plotly Dash interface with team comparisons
- **Automation**: Weekly pipeline updates with configurable scheduling
- **Configurable**: Environment variables and YAML configuration
- **Comprehensive Logging**: Detailed logs with colored console output

## Quick Start

### 1. Clone and Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/dritte-liga-table-of-justice.git
cd dritte-liga-table-of-justice

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup project
python main.py setup
```

### 2. Configure
```bash
# Copy environment template
cp .env.example .env

# Edit configuration (optional)
nano .env
```

### 3. Run Pipeline
```bash
# Process current/recent data
python main.py run

# Process specific Spieltag
python main.py run --spieltag 5
```

### 4. Start Dashboard
```bash
python main.py dashboard
```
Visit http://localhost:8050 to view the dashboard!

## Project Structure

```
3liga-table-of-justice/
├── 📄 README.md
├── 📄 requirements.txt
├── 📄 .env.example
├── 📄 main.py                  # Main CLI entry point
├── 📄 setup.py
├── 📁 src/
│   ├── 📁 scrapers/            # Web scraping modules
│   │   ├── footystats_scraper.py
│   │   └── soccerway_scraper.py
│   ├── 📁 calculators/         # xP/xG calculation logic
│   │   └── xp_calculator.py
│   ├── 📁 dashboard/           # Plotly Dash dashboard
│   │   └── app.py
│   ├── 📁 utils/               # Utilities and configuration
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── scraper_base.py
│   └── 📄 automation.py        # Main automation pipeline
├── 📁 config/
│   └── config.yaml             # Team mappings and settings
├── 📁 data/                    # Data storage (gitignored)
│   ├── footystats/
│   └── soccerway/
└── 📁 logs/                    # Application logs (gitignored)
```

## Usage Examples

### Command Line Interface

```bash
# Run full pipeline
python main.py run

# Process specific spieltag only
python main.py run --spieltag 3

# Start dashboard with custom settings
python main.py dashboard --port 8080 --debug
```

## Configuration

### Environment Variables (.env)
```bash
# Paths
BASE_DIR=./data
LOGS_DIR=./logs

# Scraping
SCRAPING_DELAY_MIN=2
SCRAPING_DELAY_MAX=8
SCRAPING_MAX_RETRIES=3

# Dashboard  
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8050
DASHBOARD_DEBUG=false

# Sources
ENABLED_SOURCES=footystats,soccerway
```

### Team Name Mappings (config/config.yaml)
The configuration includes mappings to normalize team names across different data sources:

```yaml
teams:
  "1. FC Saarbrücken": ["1 FC Saarbrucken", "Saarbrücken"]
  "FC Viktoria Köln": ["FC Viktoria Koln", "Viktoria"]
  # ... more mappings
```

## Dashboard Features

The interactive dashboard provides:

- **League Tables**: xP-based standings with position indicators
- **Performance Analysis**: Expected vs Actual points scatter plots  
- **Team Progression**: Cumulative xP over time
- **Source Comparison**: FootyStats vs Soccerway data comparison
- **Team Analysis**: Individual team performance metrics

### Pipeline Steps
1. **Fixtures Scraping**: Collect match information  
2. **xG Data Collection**: Scrape Expected Goals data
3. **xP Calculations**: Compute Expected Points using Poisson distribution
4. **Season Tables**: Update cumulative season statistics  
5. **Dashboard Refresh**: Data automatically reflects in dashboard

## Analytics Methodology

### Expected Goals (xG)
- Scraped from FootyStats.org and Soccerway.com
- Represents the quality of scoring chances
- Used as input for Expected Points calculations

### Expected Points (xP)  
- Calculated using Poisson distribution based on team xG values
- Formula considers all possible scoreline probabilities
- 3 points for win, 1 point for draw, 0 points for loss
- Provides more accurate performance measure than actual points

## Legal & Ethical Usage

**Important Disclaimer:**
- This tool scrapes publicly available data for educational/analytical purposes
- Users must respect websites' robots.txt and terms of service  
- Implement appropriate delays between requests (default: 2-8 seconds)
- Do not overload target servers with excessive requests
- Use scraped data responsibly and in compliance with applicable laws

### Rate Limiting & Best Practices
- Built-in delays and backoff strategies
- Respectful request patterns  
- User-Agent rotation
- Error handling and retries
- Configurable rate limits

## Troubleshooting

### Common Issues

**Missing Data:**
```bash
# Check if files exist
python main.py run --spieltag 1  # Start with Spieltag 1
```

**Dashboard Not Loading:**
```bash
# Check if data files exist
ls data/footystats/*.csv
ls data/soccerway/*.csv
```

### Debug Mode
```bash
# Enable detailed logging
export LOG_LEVEL=DEBUG
python main.py run --spieltag 5
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.