from bs4 import BeautifulSoup # type: ignore
import re
from datetime import datetime
import feedparser # type: ignore
from .base_scraper import BaseScraper
from config.settings import Config

class ProjectScraper(BaseScraper):
    def scrape_projects(self):
        all_projects = []
        
        for url in Config.SCRAPE_SOURCES['news']:
            try:
                feed = feedparser.parse(url)
                self.logger.info(f"Found {len(feed.entries)} entries in feed {url}")
                
                for entry in feed.entries:
                    project = self._parse_feed_entry(entry)
                    if project:
                        # More lenient matching - check if any relevant keyword is present
                        content = (project['title'] + ' ' + project['description']).lower()
                        
                        # Check for steel industry related terms
                        steel_terms = ['steel', 'metal', 'iron', 'jsw', 'jindal']
                        if any(term in content for term in steel_terms):
                            self.logger.info(f"Found relevant article: {project['title']}")
                            all_projects.append(project)
                            continue
                        
                        # Check for industry terms
                        industry_terms = ['production', 'capacity', 'plant', 'factory', 'manufacturing']
                        if any(term in content for term in industry_terms):
                            self.logger.info(f"Found relevant article: {project['title']}")
                            all_projects.append(project)
                            continue
                        
                        # Check for business terms
                        business_terms = ['profit', 'revenue', 'expansion', 'investment', 'acquisition']
                        if any(term in content for term in business_terms):
                            self.logger.info(f"Found relevant article: {project['title']}")
                            all_projects.append(project)
                            
            except Exception as e:
                self.logger.error(f"Error parsing feed {url}: {str(e)}")
                continue
        
        self.logger.info(f"Found {len(all_projects)} relevant projects/news items")
        return all_projects

    def _parse_feed_entry(self, entry):
        try:
            # Clean description by removing HTML tags
            soup = BeautifulSoup(entry.description, 'html.parser')
            description = soup.get_text().strip()
            
            # Parse date
            if hasattr(entry, 'published_parsed'):
                date = datetime(*entry.published_parsed[:6])
            else:
                date = datetime.now()
            
            # Extract budget if mentioned
            budget = self._extract_budget(description + ' ' + entry.title)
            
            # Extract keywords for better scoring
            keywords = self._extract_keywords(description + ' ' + entry.title)
            
            return {
                'title': entry.title.strip(),
                'budget': budget,
                'start_date': date,
                'description': description,
                'source': 'moneycontrol',
                'keywords': keywords,
                'keyword_count': len(keywords),  # For scoring
                'link': entry.link  # Store the link for reference
            }
        except Exception as e:
            self.logger.error(f"Error parsing feed entry: {str(e)}")
            return None

    def _extract_budget(self, text):
        # Try to find budget mentions in crores
        budget_patterns = [
            r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
            r'INR\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
            r'([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
            r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|lac)',  # Also check for lakhs
            r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*billion',  # And billions
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                budget_str = match.group(1).replace(',', '')
                value = float(budget_str)
                # Convert to crores
                if 'lakh' in pattern or 'lac' in pattern:
                    value = value / 100  # Convert lakhs to crores
                elif 'billion' in pattern:
                    value = value * 100  # Convert billions to crores
                return value
        return 0  # Default if no budget found

    def _extract_keywords(self, text):
        """Extract keywords with their context"""
        text = text.lower()
        found_keywords = []
        
        # Define keyword categories
        keywords = {
            'company': ['jsw', 'jindal', 'steel'],
            'financial': ['profit', 'revenue', 'earnings', 'results'],
            'operations': ['production', 'capacity', 'plant', 'factory'],
            'business': ['expansion', 'investment', 'acquisition', 'project'],
            'market': ['demand', 'price', 'export', 'import']
        }
        
        # Check for keywords in each category
        for category, terms in keywords.items():
            for term in terms:
                if term in text:
                    # Get surrounding context
                    pattern = f".{{0,50}}{term}.{{0,50}}"
                    match = re.search(pattern, text)
                    if match:
                        found_keywords.append(f"{category.title()}: {term}")
        
        return found_keywords