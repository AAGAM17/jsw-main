import logging
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any
import requests
from config.settings import Config
from .contact_enricher import ContactEnricher
from .email_handler import EmailHandler
import re
from bs4 import BeautifulSoup
import time

class Agent:
    def __init__(self, name: str, instructions: str, functions: List[callable]):
        self.name = name
        self.instructions = instructions
        self.functions = functions
        self.logger = logging.getLogger(f"agent.{name}")

class ProjectDiscoverySystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.contact_enricher = ContactEnricher()
        self.email_handler = EmailHandler()
        
        # Initialize Firecrawl headers
        self.firecrawl_headers = {
            'Authorization': f'Bearer {Config.FIRECRAWL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Initialize agents
        self.agents = self._initialize_agents()
        
    def _initialize_agents(self) -> Dict[str, Agent]:
        """Initialize the agent system with enhanced instructions"""
        
        def handoff_to_search_google():
            return self.agents['search']
            
        def handoff_to_map_url():
            return self.agents['mapper']
            
        def handoff_to_website_scraper():
            return self.agents['scraper']
            
        def handoff_to_analyst():
            return self.agents['analyst']
        
        interface_instructions = """
        Automatically detect and analyze recent Indian infrastructure projects requiring steel supply.
        Daily search parameters:
        1. Find all contract awards in last 1 day 
        2. Identify new project announcements with steel requirements
    
 
        
        Priority sectors:
        - Road/Rail Infrastructure 
        - Metro projects
        - Commercial Real Estate
        - Industrial Parks
        - Port Developments
        - any other infrastructure projects where steel would be required
        
        Auto-filter criteria:
        - Indian developers/contractors
        
      
        """
        
        search_instructions = """
        Use these search patterns:
        “Infrastructure contract wins” "steel supply" 
        “Railway contract wins” “highway contract wins” 
        "tender result" “metro contract wins“ 
        “Metro rail tender wins“ “highway construction contract wins” “Port development contract wins”
        “EPC contract wins”
        
        Site-specific searches:
        site:epc.gov.in "awarded to" AND "steel"
        site:nseindia.com "contract win" AND "construction"
        site:nhai.gov.in "tender result"
        site:constructionworld.in "project update"
        site:themetrorailguy.com "contract awarded"
        
        Company-specific patterns:
        "[company name] wins [project type]"
        "steel requirement" AND "TMT" OR "HR plates"
        "procurement timeline" AND "steel"
        
     
        """
        
        mapper_instructions = """
        Prioritize mapping of:
        - Government tender portals (epc.gov.in, nhai.gov.in)
        - Company investor relations pages
        - Stock exchange filings
        - Verified industry news portals
        
        Focus on:
        - PDF documents with contract details
        - Press releases with procurement information
        - Project timelines and steel requirements
        - Contact information of procurement teams
        
        JSW-specific mapping:
        - Track competitor supply agreements
        - Monitor customer announcements
        - Map project locations to JSW plant proximity
        """
        
        scraper_instructions = """
        Extract detailed project information focusing on:
        1. Contract award details and dates
        2. Steel requirements breakdown by type
        3. Project timelines and milestones
      
        
        Special attention to:
        - Delivery schedules
    
        
        Format data for priority analysis:
        - High priority indicators
        - Strategic importance factors
        """
        
        analyst_instructions = """
        Extract structured data from content with focus on:
        1. Project value (INR crores)
        2. Steel requirement (metric tons)
        3. Procurement timeline
        4. Contract award date
        5. Key decision makers
        
        Validate financial figures against project scope.
        Calculate approximate steel needs using:
        - High-rise construction: 60kg/sqft
        - Infrastructure projects: 100-150kg/lane-km
        - Metro projects: 150-200kg/meter
        - Industrial structures: 80-100kg/sqft
        
       
        
        Priority scoring based on:
        - Project value and steel requirement
        - Timeline urgency

       
        
        Format results with:
        - Verified source links
        - Contact information
        - Relationship history
        - Priority indicators
        - Action recommendations
        """

        return {
            'interface': Agent("Steel Opportunity Interface", interface_instructions, [handoff_to_search_google]),
            'search': Agent("Steel Project Search Agent", search_instructions, [self._search_google, handoff_to_map_url]),
            'mapper': Agent("Government & Corporate Source Mapper", mapper_instructions, [self._map_url_pages, handoff_to_website_scraper]),
            'scraper': Agent("Website Scraper Agent", scraper_instructions, [self._scrape_url, handoff_to_analyst]),
            'analyst': Agent("Steel Opportunity Analyst", analyst_instructions, [self._analyze_website_content])
        }
    
    def discover_opportunities(self) -> List[Dict[str, Any]]:
        """Main method to discover and process new opportunities"""
        try:
            # Start with interface agent
            interface_agent = self.agents['interface']
            self.logger.info(f"Starting opportunity discovery with {interface_agent.name}")
            
            # Get search results
            search_agent = interface_agent.functions[0]()
            search_results = search_agent.functions[0]()
            
            # Process each search result
            opportunities = []
            for result in search_results:
                try:
                    # Map URLs
                    mapper_agent = search_agent.functions[1]()
                    mapped_urls = mapper_agent.functions[0](result)
                    
                    # Scrape content
                    scraper_agent = mapper_agent.functions[1]()
                    content = scraper_agent.functions[0](mapped_urls)
                    
                    # Analyze content
                    analyst_agent = scraper_agent.functions[1]()
                    opportunity = analyst_agent.functions[0](content)
                    
                    if self._validate_opportunity(opportunity):
                        # Enrich with contact information using ContactOut
                        self.logger.info(f"Enriching opportunity with contact information...")
                        contact_info = self.contact_enricher.enrich_project_contacts(opportunity)
                        
                        if contact_info['status'] == 'success':
                            opportunity['contacts'] = contact_info['contacts']
                            opportunity['relationship'] = contact_info['relationship']
                            opportunity['priority'] = contact_info['priority']
                            self.logger.info(f"Successfully enriched opportunity with {len(contact_info['contacts'])} contacts")
                        else:
                            self.logger.warning(f"Contact enrichment failed: {contact_info['message']}")
                            
                        opportunities.append(opportunity)
                        
                except Exception as e:
                    self.logger.error(f"Error processing search result: {str(e)}")
                    continue
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error in opportunity discovery: {str(e)}")
            return []
    
    def _search_google(self) -> List[Dict[str, Any]]:
        """Execute SERP API search with retries"""
        try:
            headers = {
                'Authorization': f'Bearer {Config.SERP_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            all_results = []
            
            # 1. Search Google Web Results
            for query in Config.SERP_SETTINGS['search_queries']:
                try:
                    # Add company names to query for better targeting
                    company_names = [
                        company['name']
                        for category in Config.PROJECT_DISCOVERY['target_companies'].values()
                        for company in category
                    ]
                    
                    # Create company-specific queries
                    for company in company_names:
                        company_query = f'"{company}" {query}'
                        
                        response = requests.get(
                            'https://serpapi.com/search',
                            params={
                                'q': company_query,
                                **Config.SERP_SETTINGS['search_parameters']
                            },
                            headers=headers
                        )
                        
                        response.raise_for_status()
                        data = response.json()
                        
                        if 'organic_results' in data:
                            all_results.extend(data['organic_results'])
                            
                except Exception as e:
                    self.logger.error(f"Error in SERP API search for query '{query}': {str(e)}")
                    continue
            
            # 2. Search Google News
            for query in Config.SERP_SETTINGS['search_queries']:
                try:
                    response = requests.get(
                        'https://serpapi.com/search',
                        params={
                            'q': query,
                            **Config.SERP_SETTINGS['news_parameters']
                        },
                        headers=headers
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'news_results' in data:
                        all_results.extend(data['news_results'])
                        
                except Exception as e:
                    self.logger.error(f"Error in SERP News API search for query '{query}': {str(e)}")
                    continue
            
            # 3. Scrape company announcement pages
            for category in Config.PROJECT_DISCOVERY['target_companies'].values():
                for company in category:
                    for url in company['announcement_urls']:
                        try:
                            # Use Firecrawl to scrape announcement pages
                            response = requests.post(
                                'https://api.firecrawl.io/extract',
                                headers=self.firecrawl_headers,
                                json={
                                    'url': url,
                                    'elements': {
                                        'announcements': {
                                            'selectors': [
                                                '.news-item',
                                                '.announcement',
                                                '.media-item',
                                                'article'
                                            ]
                                        }
                                    },
                                    **Config.FIRECRAWL_SETTINGS['extraction_options']
                                }
                            )
                            
                            response.raise_for_status()
                            data = response.json()
                            
                            if 'announcements' in data:
                                announcements = data['announcements']
                                for announcement in announcements:
                                    # Add company context to the announcement
                                    announcement['company'] = company['name']
                                    announcement['source'] = 'company_announcement'
                                    all_results.append(announcement)
                                    
                        except Exception as e:
                            self.logger.error(f"Error scraping announcement page {url}: {str(e)}")
                            continue
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            
            for result in all_results:
                url = result.get('link') or result.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_results.append(result)
            
            return unique_results
            
        except Exception as e:
            self.logger.error(f"Error in search operations: {str(e)}")
            return []
    
    def _map_url_pages(self, search_results: List[Dict[str, Any]]) -> List[str]:
        """Map search results to relevant URLs"""
        try:
            mapped_urls = []
            for result in search_results:
                url = result.get('link')
                if url and self._is_relevant_url(url):
                    mapped_urls.append(url)
            return mapped_urls
        except Exception as e:
            self.logger.error(f"Error mapping URLs: {str(e)}")
            return []
    
    def _is_relevant_url(self, url: str) -> bool:
        """Check if URL is from a relevant source"""
        relevant_domains = [
            'constructionworld.in',
            'themetrorailguy.com',
            'epc.gov.in',
            'nhai.gov.in',
            'nseindia.com'
        ]
        return any(domain in url.lower() for domain in relevant_domains)
    
    def _scrape_url(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape content from URLs using Firecrawl"""
        try:
            # Test Firecrawl API connection first
            try:
                test_response = requests.get(
                    'https://api.firecrawl.com/v1/test',
                    headers=self.firecrawl_headers,
                    timeout=10
                )
                test_response.raise_for_status()
                firecrawl_available = True
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Firecrawl API test failed: {str(e)}")
                firecrawl_available = False

            if not firecrawl_available:
                self.logger.warning("Falling back to basic scraping")
                return [self._basic_scrape(url) for url in urls]

            scraped_content = []
            max_retries = 3
            
            for url in urls:
                for attempt in range(max_retries):
                    try:
                        # Use Firecrawl's extraction API
                        response = requests.post(
                            'https://api.firecrawl.com/v1/extract',
                            headers=self.firecrawl_headers,
                            json={
                                'url': url,
                                'options': Config.FIRECRAWL_SETTINGS['extraction_options'],
                                'elements': {
                                    'project_details': {
                                        'selectors': Config.FIRECRAWL_SETTINGS['extraction_rules']['project_details']
                                    },
                                    'contact_info': {
                                        'selectors': Config.FIRECRAWL_SETTINGS['extraction_rules']['contact_info']
                                    },
                                    'dates': {
                                        'selectors': Config.FIRECRAWL_SETTINGS['extraction_rules']['dates']
                                    },
                                    'specifications': {
                                        'selectors': Config.FIRECRAWL_SETTINGS['extraction_rules']['specifications']
                                    }
                                }
                            },
                            timeout=15
                        )
                        response.raise_for_status()
                        
                        # Process the response
                        content = self._process_firecrawl_response(response.json(), url)
                        if content:
                            scraped_content.append(content)
                        break
                        
                    except requests.exceptions.RequestException as e:
                        self.logger.warning(f"Firecrawl attempt {attempt + 1} failed for {url}: {str(e)}")
                        if attempt == max_retries - 1:
                            # If all retries fail, fall back to basic scraping
                            self.logger.warning(f"Falling back to basic scraping for {url}")
                            content = self._basic_scrape(url)
                            if content:
                                scraped_content.append(content)
                        else:
                            time.sleep(2)  # Wait before retry
                            
            return scraped_content
            
        except Exception as e:
            self.logger.error(f"Error in _scrape_url: {str(e)}")
            return []
    
    def _process_firecrawl_response(self, data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Process the Firecrawl API response"""
        try:
            processed_data = {
                'url': url,
                'content': {},
                'metadata': {}
            }
            
            # Extract project details
            if project_content := data.get('project_details', {}).get('content'):
                processed_data['content']['project_details'] = project_content
                
                # Try to extract project value
                value_matches = re.findall(r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)', project_content)
                if value_matches:
                    processed_data['metadata']['project_value'] = float(value_matches[0].replace(',', ''))
                
                # Try to extract steel requirements
                steel_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)', project_content)
                if steel_matches:
                    processed_data['metadata']['steel_requirement'] = float(steel_matches[0].replace(',', ''))
            
            # Extract contact information
            if contact_content := data.get('contact_info', {}).get('content'):
                processed_data['content']['contact_info'] = contact_content
                
                # Try to extract email addresses
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', contact_content)
                if emails:
                    processed_data['metadata']['contact_emails'] = emails
                
                # Try to extract phone numbers
                phones = re.findall(r'(?:\+91|0)?[789]\d{9}', contact_content)
                if phones:
                    processed_data['metadata']['contact_phones'] = phones
            
            # Extract dates
            if dates_content := data.get('dates', {}).get('content'):
                processed_data['content']['dates'] = dates_content
                
                # Try to extract project timeline
                date_matches = re.findall(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}', dates_content)
                if len(date_matches) >= 2:
                    processed_data['metadata']['start_date'] = datetime.strptime(date_matches[0], '%B %Y')
                    processed_data['metadata']['end_date'] = datetime.strptime(date_matches[1], '%B %Y')
            
            # Extract specifications
            if specs_content := data.get('specifications', {}).get('content'):
                processed_data['content']['specifications'] = specs_content
                
                # Try to extract steel types
                steel_types = {
                    'TMT': re.findall(r'TMT[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)', specs_content),
                    'HR_Plates': re.findall(r'HR[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)', specs_content)
                }
                if any(steel_types.values()):
                    processed_data['metadata']['steel_types'] = steel_types
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Error processing Firecrawl response: {str(e)}")
            return None
    
    def _basic_scrape(self, url: str) -> Dict[str, Any]:
        """Basic scraping fallback method"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.select('script, style, iframe, nav, footer, header, aside'):
                element.decompose()
            
            # Get main content
            main_content = ''
            for tag in ['article', '.entry-content', '.post-content', 'main']:
                if content := soup.select_one(tag):
                    main_content = content.get_text(strip=True)
                    break
            
            if not main_content:
                main_content = soup.get_text(strip=True)
            
            return {
                'url': url,
                'content': {'raw_text': main_content},
                'metadata': {}
            }
            
        except Exception as e:
            self.logger.error(f"Error in basic scraping for {url}: {str(e)}")
            return None
    
    def _analyze_website_content(self, content_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze scraped content for project opportunities"""
        try:
            opportunities = []
            for content in content_list:
                try:
                    opportunity = self._extract_project_info(content)
                    if opportunity:
                        opportunities.append(opportunity)
                except Exception as e:
                    self.logger.error(f"Error analyzing content from {content['url']}: {str(e)}")
                    continue
            return opportunities
        except Exception as e:
            self.logger.error(f"Error in content analysis: {str(e)}")
            return []
    
    def _extract_project_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract project information from content"""
        try:
            project_info = {}
            
            # Extract basic project details
            raw_text = content.get('content', {}).get('raw_text', '')
            project_details = content.get('content', {}).get('project_details', '')
            full_text = f"{raw_text}\n{project_details}"
            
            # Extract company name
            company_patterns = [
                r'([A-Za-z\s]+(?:Limited|Ltd|Corporation|Corp|Infrastructure|Infratech|Construction|Constructions|Engineering))',
                r'([A-Za-z\s]+) has been awarded',
                r'([A-Za-z\s]+) wins',
                r'contract to ([A-Za-z\s]+)',
                r'([A-Za-z\s]+) emerges',
                r'([A-Za-z\s]+) bags'
            ]
            
            for pattern in company_patterns:
                if match := re.search(pattern, full_text):
                    project_info['company'] = match.group(1).strip()
                    break
            
            # Extract project title
            title_patterns = [
                r'project titled "([^"]+)"',
                r'project named "([^"]+)"',
                r'awarded ([^\.]+) project',
                r'construction of ([^\.]+)'
            ]
            
            for pattern in title_patterns:
                if match := re.search(pattern, full_text):
                    project_info['title'] = match.group(1).strip()
                    break
            
            # Extract project value
            value_patterns = [
                r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
                r'worth\s*(?:Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
                r'value\s*of\s*(?:Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)'
            ]
            
            for pattern in value_patterns:
                if match := re.search(pattern, full_text, re.IGNORECASE):
                    try:
                        project_info['value'] = float(match.group(1).replace(',', ''))
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
                dates.extend(re.findall(pattern, full_text))
            
            if dates:
                if len(dates) >= 2:
                    try:
                        project_info['start_date'] = datetime.strptime(dates[0], '%B %Y')
                        project_info['end_date'] = datetime.strptime(dates[1], '%B %Y')
                    except ValueError:
                        try:
                            project_info['start_date'] = datetime.strptime(dates[0], '%d %B %Y')
                            project_info['end_date'] = datetime.strptime(dates[1], '%d %B %Y')
                        except ValueError:
                            project_info['start_date'] = datetime.strptime(dates[0], '%b %Y')
                            project_info['end_date'] = datetime.strptime(dates[1], '%b %Y')
                else:
                    try:
                        project_info['start_date'] = datetime.strptime(dates[0], '%B %Y')
                        project_info['end_date'] = project_info['start_date'] + timedelta(days=365*2)
                    except ValueError:
                        try:
                            project_info['start_date'] = datetime.strptime(dates[0], '%d %B %Y')
                            project_info['end_date'] = project_info['start_date'] + timedelta(days=365*2)
                        except ValueError:
                            project_info['start_date'] = datetime.strptime(dates[0], '%b %Y')
                            project_info['end_date'] = project_info['start_date'] + timedelta(days=365*2)
            
            # Extract steel requirement
            steel_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                r'steel\s*requirement\s*of\s*(\d+(?:,\d+)*(?:\.\d+)?)',
                r'steel\s*quantity\s*:\s*(\d+(?:,\d+)*(?:\.\d+)?)'
            ]
            
            for pattern in steel_patterns:
                if match := re.search(pattern, full_text, re.IGNORECASE):
                    try:
                        project_info['steel_requirement'] = float(match.group(1).replace(',', ''))
                        break
                    except ValueError:
                        continue
            
            # Add source URL
            project_info['source_url'] = content.get('url', '')
            
            # Add description
            project_info['description'] = full_text[:500] if full_text else ''
            
            return project_info
            
        except Exception as e:
            self.logger.error(f"Error extracting project info: {str(e)}")
            return None
    
    def _validate_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Validate if opportunity meets criteria"""
        try:
            if not opportunity:
                return False
                
            # Check project value
            value_in_cr = opportunity.get('value', 0)
            if value_in_cr < 500:  # 500 crore minimum
                return False
            
            # Check steel requirement
            steel_req = opportunity.get('steel_requirement', 0)
            if steel_req < 5000:  # 5000 MT minimum
                return False
            
            # Check timeline
            start_date = opportunity.get('start_date')
            if start_date:
                months_to_start = (start_date - datetime.now()).days / 30
                if months_to_start > 6:  # Within 6 months
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating opportunity: {str(e)}")
            return False 