import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin
import urllib3
import certifi
import time
from typing import List, Dict

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class MetroScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.base_url = 'https://www.metrorailnews.in'
        
        # Configure session to use system CA certificates
        self.session.verify = certifi.where()
        
        # Configure retry strategy
        retry_strategy = urllib3.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.categories = [
            '/category/metro-rail-news',
            '/category/metro-rail-tenders',
            '/category/metro-rail-contracts'
        ]
    
    def scrape_latest_news(self) -> List[Dict]:
        all_articles = []
        
        for category in self.categories:
            try:
                url = f"{self.base_url}{category}"
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all('article')
                
                for article in articles:
                    try:
                        # Extract title and link
                        title_elem = article.find('h2', class_='entry-title')
                        if not title_elem or not title_elem.find('a'):
                            continue
                            
                        title = title_elem.find('a').text.strip()
                        link = title_elem.find('a')['href']
                        
                        # Extract date
                        date_elem = article.find('time', class_='entry-date')
                        date_str = date_elem['datetime'] if date_elem else None
                        
                        try:
                            date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if date_str else datetime.now()
                        except ValueError:
                            date = datetime.now()
                            
                        # Extract description
                        desc_elem = article.find('div', class_='entry-content')
                        description = desc_elem.text.strip() if desc_elem else ''
                        
                        # Create article dict
                        article_data = {
                            'title': title,
                            'description': description,
                            'source_url': link,
                            'source': 'metro_news',
                            'value': 0,  # Will be enriched later
                            'company': '',  # Will be enriched later
                            'start_date': date,
                            'end_date': date,
                            'news_date': date
                        }
                        
                        all_articles.append(article_data)
                        
                    except Exception as e:
                        logger.error(f"Error processing article: {str(e)}")
                        continue
                        
                time.sleep(2)  # Add delay between category requests
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                continue
                
        logger.info(f"Found {len(all_articles)} articles from metro news")
        return all_articles
    
    def _scrape_article(self, url, title):
        try:
            response = self.session.get(
                url,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': self.base_url
                }
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content = soup.find('div', class_='entry-content')
            if not content:
                return None
                
            text = content.get_text()
            
            # Extract company name
            company_patterns = [
                r'([A-Za-z\s]+(?:Limited|Ltd|Corporation|Corp|Infrastructure|Infratech|Construction|Constructions|Engineering))',
                r'([A-Za-z\s]+) has been awarded',
                r'([A-Za-z\s]+) wins',
                r'contract to ([A-Za-z\s]+)',
                r'([A-Za-z\s]+) emerges',
                r'([A-Za-z\s]+) bags'
            ]
            
            company = None
            for pattern in company_patterns:
                if match := re.search(pattern, text):
                    company = match.group(1).strip()
                    break
            
            # Extract value
            value_patterns = [
                r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
                r'([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
                r'worth\s*Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
                r'value\s*of\s*Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)'
            ]
            
            value = None
            for pattern in value_patterns:
                if match := re.search(pattern, text, re.IGNORECASE):
                    try:
                        value = float(match.group(1).replace(',', ''))
                        break
                    except ValueError:
                        continue
            
            # Extract dates
            date_patterns = [
                r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
                r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
            ]
            
            dates = []
            for pattern in date_patterns:
                dates.extend(re.findall(pattern, text))
            
            start_date = None
            end_date = None
            
            if dates:
                if len(dates) >= 2:
                    try:
                        start_date = datetime.strptime(dates[0], '%B %Y')
                    except ValueError:
                        try:
                            start_date = datetime.strptime(dates[0], '%d %B %Y')
                        except ValueError:
                            start_date = datetime.strptime(dates[0], '%b %Y')
                            
                    try:
                        end_date = datetime.strptime(dates[1], '%B %Y')
                    except ValueError:
                        try:
                            end_date = datetime.strptime(dates[1], '%d %B %Y')
                        except ValueError:
                            end_date = datetime.strptime(dates[1], '%b %Y')
                            
                elif len(dates) == 1:
                    try:
                        start_date = datetime.strptime(dates[0], '%B %Y')
                    except ValueError:
                        try:
                            start_date = datetime.strptime(dates[0], '%d %B %Y')
                        except ValueError:
                            start_date = datetime.strptime(dates[0], '%b %Y')
                            
                    end_date = start_date.replace(year=start_date.year + 3)  # Assume 3 years for completion
            
            if company and value:
                return {
                    'company': company,
                    'title': title.replace(company, '').strip('. '),
                    'value': value,
                    'start_date': start_date or datetime.now(),
                    'end_date': end_date or datetime.now().replace(year=datetime.now().year + 3),
                    'source_url': url,
                    'description': text[:500]  # First 500 chars as description
                }
            
        except Exception as e:
            self.logger.error(f"Error scraping article {url}: {str(e)}")
        
        return None 