from bs4 import BeautifulSoup # type: ignore
import re
from datetime import datetime, timedelta
import requests
from .base_scraper import BaseScraper
from .perplexity_client import PerplexityClient
from config.settings import Config
import json
import logging

class InfraProjectScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.existing_projects = self._load_existing_projects()
        self.perplexity = PerplexityClient()

    def _load_existing_projects(self):
        """Load database of existing JSW Steel projects"""
        try:
            with open(Config.EXISTING_PROJECTS_DB, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning("No existing projects database found")
            return []

    def scrape_projects(self):
        """Main scraping method that coordinates different sources"""
        all_projects = []
        
        # 1. Scrape themetrorailguy.com for reliable metro project data
        self.logger.info("Scraping themetrorailguy.com for metro projects...")
        metro_projects = self._scrape_metro_projects()
        all_projects.extend(metro_projects)
        
        # 2. Use Perplexity AI for discovering other infrastructure projects
        self.logger.info("Using Perplexity AI to discover infrastructure projects...")
        ai_discovered_projects = self.perplexity.research_infrastructure_projects()
        all_projects.extend(ai_discovered_projects)
        
        # Filter out existing projects
        filtered_projects = self._filter_existing_projects(all_projects)
        
        # Enrich with procurement info
        enriched_projects = self._enrich_with_procurement_info(filtered_projects)
        
        # Sort by priority
        sorted_projects = self._sort_by_priority(enriched_projects)
        
        return sorted_projects

    def _scrape_metro_projects(self):
        """Scrape metro rail projects from themetrorailguy.com"""
        projects = []
        url = Config.METRO_SOURCES['themetrorailguy']
        
        try:
            html = self.fetch_page(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                tender_articles = soup.find_all('article', class_='post')
                
                for article in tender_articles:
                    project = self._parse_metro_article(article)
                    if project:
                        projects.append(project)
        except Exception as e:
            self.logger.error(f"Error scraping metro projects: {str(e)}")
        
        return projects

    def _parse_metro_article(self, article):
        """Parse metro project article from themetrorailguy.com"""
        try:
            # Extract title
            title_elem = article.find('h2', class_='entry-title')
            if not title_elem:
                return None
                
            title = title_elem.text.strip()
            link = title_elem.find('a')['href']
            
            # Get full article content
            article_html = self.fetch_page(link)
            if not article_html:
                return None
                
            article_soup = BeautifulSoup(article_html, 'html.parser')
            content = article_soup.find('div', class_='entry-content')
            
            if not content:
                return None
                
            text = content.get_text()
            
            # Extract project value
            value = self._extract_project_value(text)
            
            # Extract dates
            start_date, end_date = self._extract_project_dates(text)
            
            # Only include if we found a value
            if not value:
                return None
            
            return {
                'title': title,
                'description': text[:500],  # First 500 chars as description
                'value': value,
                'start_date': start_date or datetime.now(),
                'end_date': end_date or (datetime.now() + timedelta(days=365)),
                'source': 'themetrorailguy',
                'source_url': link,
                'steel_requirement': self._estimate_steel_requirement(text, value)
            }
        except Exception as e:
            self.logger.error(f"Error parsing metro article: {str(e)}")
            return None

    def _filter_existing_projects(self, projects):
        """Filter out projects that JSW is already supplying to"""
        filtered = []
        for project in projects:
            if not any(self._is_same_project(project, existing) for existing in self.existing_projects):
                filtered.append(project)
        return filtered

    def _is_same_project(self, project1, project2):
        """Compare projects to check if they're the same"""
        # Compare based on title similarity
        title1 = project1.get('title', '').lower()
        title2 = project2.get('title', '').lower()
        
        # Simple word overlap comparison
        words1 = set(title1.split())
        words2 = set(title2.split())
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        similarity = overlap / total if total > 0 else 0
        return similarity > 0.7  # 70% word overlap threshold

    def _enrich_with_procurement_info(self, projects):
        """Add procurement team information to projects"""
        for project in projects:
            try:
                procurement_info = self._get_procurement_info(project)
                project['procurement_team'] = procurement_info
            except Exception as e:
                self.logger.error(f"Error enriching project with procurement info: {str(e)}")
        return projects

    def _get_procurement_info(self, project):
        """Get procurement team information using various sources"""
        # Implementation will vary based on available sources
        pass

    def _sort_by_priority(self, projects):
        """Sort projects by priority based on start time and value"""
        def priority_score(project):
            # Calculate months until project start
            months_to_start = (project['start_date'] - datetime.now()).days / 30
            
            # Projects starting sooner get higher priority
            time_score = 1 / (months_to_start + 1)  # Add 1 to avoid division by zero
            
            # Larger projects get higher priority
            value_score = project['value'] / 1000  # Normalize to thousands of crores
            
            # Combined score with time having more weight
            return (time_score * 0.7) + (value_score * 0.3)
        
        return sorted(projects, key=priority_score, reverse=True)

    def _estimate_steel_requirement(self, description, project_value):
        """Estimate steel requirement based on project description and value"""
        if not project_value:
            return None
            
        # Get appropriate factor based on project type
        factor = None
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['metro', 'railway', 'rail']):
            factor = Config.STEEL_FACTORS['metro']
        elif any(word in desc_lower for word in ['bridge', 'viaduct']):
            factor = Config.STEEL_FACTORS['bridge']
        elif any(word in desc_lower for word in ['building', 'complex', 'tower']):
            factor = Config.STEEL_FACTORS['building']
        else:
            factor = Config.STEEL_FACTORS['default']
        
        return project_value * factor

    def _extract_project_value(self, text):
        """Extract project value from text"""
        # Look for amounts in crores
        crore_patterns = [
            r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
            r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
            r'worth\s*(?:Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)'
        ]
        
        for pattern in crore_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                try:
                    return float(match.group(1).replace(',', ''))
                except ValueError:
                    continue
        
        return None

    def _extract_project_dates(self, text):
        """Extract project start and end dates from text"""
        try:
            # Look for date patterns
            date_pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (?:\d{1,2},? )?\d{4}'
            dates = re.findall(date_pattern, text)
            
            start_date = None
            end_date = None
            
            if dates:
                if len(dates) >= 2:
                    start_date = datetime.strptime(dates[0], '%B %Y')
                    end_date = datetime.strptime(dates[1], '%B %Y')
                elif len(dates) == 1:
                    start_date = datetime.strptime(dates[0], '%B %Y')
                    end_date = start_date + timedelta(days=365)  # Assume 1 year duration
            
            return start_date, end_date
            
        except Exception as e:
            self.logger.error(f"Error extracting dates: {str(e)}")
            return None, None 
