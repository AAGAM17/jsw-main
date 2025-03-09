# Project Discovery Workflow

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [System Requirements](#system-requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Project Structure](#project-structure)
7. [Workflow Stages](#workflow-stages)
8. [API Keys and Dependencies](#api-keys-and-dependencies)
9. [Usage Examples](#usage-examples)
10. [Troubleshooting](#troubleshooting)
11. [Contributing](#contributing)

## Overview

The Project Discovery Workflow is an automated system for discovering, analyzing, and tracking infrastructure and construction projects in India. It uses multiple data sources, advanced filtering, and AI-powered enrichment to provide high-quality project leads with detailed steel requirements.

### Key Benefits
- Automated project discovery from multiple sources
- Intelligent filtering and validation
- Detailed steel requirement calculations
- Priority scoring and categorization
- Automated notifications via email and WhatsApp

## Features

### 1. Multi-Source Project Discovery
- BSE (Bombay Stock Exchange) Announcements
- Company Websites (via Firecrawl)
- Metro Project Updates
- Google News (via Serper API)

### 2. Smart Filtering
- Relevancy checking
- Date validation
- Company verification
- Value extraction
- Duplicate removal

### 3. Project Enrichment
- Steel requirement calculations
- Contact information discovery
- Timeline analysis
- Location extraction
- Project type classification

### 4. Priority Scoring
- Value-based scoring
- Timeline-based urgency
- Steel requirement weighting
- Automated tagging

### 5. Notifications
- Email notifications
- WhatsApp updates
- Priority-based alerts

## System Requirements

- Python 3.8+
- Required Python packages (see requirements.txt)
- API Keys:
  - Serper API
  - Groq API
  - Firecrawl API

## Installation

1. Clone the repository:
\`\`\`bash
git clone <repository-url>
cd project-discovery
\`\`\`

2. Create and activate virtual environment:
\`\`\`bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
\`\`\`

3. Install dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

## Configuration

1. Create a \`.env\` file in the root directory:
\`\`\`env
SERPER_API_KEY=your_serper_api_key
GROQ_API_KEY=your_groq_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
\`\`\`

2. Configure email settings in \`config/settings.py\`:
\`\`\`python
Config.EMAIL_SETTINGS = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'username': 'your_email@gmail.com',
    'password': 'your_app_password'
}
\`\`\`

## Project Structure

\`\`\`
project-discovery/
├── utilities/
│   ├── project_discovery_graph.py    # Main workflow implementation
│   ├── contact_finder.py            # Contact discovery logic
│   └── email_handler.py             # Email notification handling
├── scrapers/
│   └── metro_scraper.py            # Metro project scraping
├── whatsapp/
│   └── interakt_handler.py         # WhatsApp notification handling
├── config/
│   └── settings.py                 # Configuration settings
├── requirements.txt                # Project dependencies
└── README.md                      # This documentation
\`\`\`

## Workflow Stages

### 1. Project Scraping (`scrape_projects`)
- Fetches projects from multiple sources
- Combines and deduplicates results
- Initial data structuring

### 2. Project Filtering (`filter_projects`)
- Validates project data
- Removes outdated projects
- Checks for relevancy
- Extracts key information

### 3. Project Enrichment (`enrich_projects`)
- Calculates steel requirements based on:
  - Project type
  - Project value
  - Specifications (length, area, floors)
- Categories:
  - Primary Steel (TMT Bars, Hot Rolled)
  - Secondary Steel (Hot Rolled, Cold Rolled)
  - Tertiary Steel (Wire Rods)
- Finds contact information
- Extracts location data

### 4. Project Prioritization (`prioritize_projects`)
- Calculates priority scores based on:
  - Project value
  - Timeline urgency
  - Steel requirements
- Adds tags:
  - Urgent Priority (start within 3 months)
  - High Priority (start within 6 months)
  - Normal Priority (others)
  - Major Project (value ≥ 1000 cr)
  - Large Project (value ≥ 500 cr)
  - High Steel Requirement (≥ 10000 MT)

### 5. Notifications (`send_notifications`)
- Sends email notifications
- Sends WhatsApp updates
- Includes priority information

## API Keys and Dependencies

### Required APIs:
1. **Serper API** (Google Search Results)
   - Sign up at: https://serper.dev
   - Used for: Web scraping project information

2. **Groq API** (AI Processing)
   - Sign up at: https://groq.com
   - Used for: Text analysis and headline generation

3. **Firecrawl API** (Optional)
   - Used for: Advanced web scraping

### Main Dependencies:
- langgraph: Workflow management
- beautifulsoup4: HTML parsing
- requests: HTTP requests
- groq: AI text processing
- pydantic: Data validation

## Usage Examples

### Basic Usage
\`\`\`python
from utilities.project_discovery_graph import run_workflow

# Run the complete workflow
result = run_workflow()

# Access discovered projects
projects = result['prioritized_projects']

# Check workflow status
status = result['status']
\`\`\`

### Custom Configuration
\`\`\`python
from config.settings import Config

# Configure API keys
Config.SERPER_API_KEY = 'your_key'
Config.GROQ_API_KEY = 'your_key'

# Configure priority weights
Config.PRIORITY_WEIGHTS = {
    'time_factor': 0.6,
    'value_factor': 0.4
}

# Run workflow
result = run_workflow()
\`\`\`

## Troubleshooting

### Common Issues:

1. **API Key Errors**
   - Ensure all required API keys are set in .env file
   - Check API key validity and quotas

2. **Scraping Issues**
   - Check internet connectivity
   - Verify source URLs are accessible
   - Review rate limiting settings

3. **Notification Errors**
   - Verify email configuration
   - Check WhatsApp integration settings
   - Ensure proper permissions

### Debug Logging
- Logs are written to 'project_discovery.log'
- Set logging level in code:
\`\`\`python
import logging
logging.getLogger('project_discovery').setLevel(logging.DEBUG)
\`\`\`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

### Coding Standards
- Follow PEP 8 guidelines
- Add docstrings to functions
- Include type hints
- Write unit tests for new features 