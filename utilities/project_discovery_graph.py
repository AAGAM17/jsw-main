"""Project discovery workflow implementation using LangGraph."""

from typing import Annotated, Optional, Sequence, TypedDict, Union, List, Dict
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
import operator
from datetime import datetime, timedelta
import logging
import requests
import json
from groq import Groq
from .contact_finder import ContactFinder
from urllib.parse import urlparse
from dataclasses import dataclass
import time
from config.settings import Config
from .email_handler import EmailHandler
from whatsapp.interakt_handler import InteraktHandler
from scrapers.metro_scraper import MetroScraper
import re
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('project_discovery.log')  # Log to file
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Define configuration if not in Config
if not hasattr(Config, 'SERPER_API_KEY'):
    Config.SERPER_API_KEY = '1e8c5d0c76e91be182cdd3648616ca58cf88a6a0'  # Your provided API key

if not hasattr(Config, 'GROQ_API_KEY'):
    Config.GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

if not hasattr(Config, 'SERPER_SETTINGS'):
    Config.SERPER_SETTINGS = {
        'exclude_domains': [
            'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
            'youtube.com', 'pinterest.com', 'reddit.com', 'medium.com'
        ]
    }

# Define state types
class ProjectData(TypedDict):
    """Type definition for project data."""
    title: str
    description: str
    source_url: str
    source: str
    value: float
    company: str
    start_date: datetime
    end_date: datetime
    steel_requirements: dict
    teams: list
    priority_score: int
    contacts: list

class WorkflowState(TypedDict):
    """Type definition for workflow state."""
    projects: list[ProjectData]
    filtered_projects: list[ProjectData]
    enriched_projects: list[ProjectData]
    prioritized_projects: list[ProjectData]
    error: Union[str, None]
    status: str

def extract_company_name(text: str) -> Union[str, None]:
    """Extract company name from text."""
    patterns = [
        r'(?:M/s\.|M/s|Messrs\.)?\s*([A-Za-z\s&\.]+(?:Limited|Ltd|Corporation|Corp|Infrastructure|Infra|Construction|Engineering|Projects|Builders|Industries|Enterprises|Company|Pvt|Private|Public))',
        r'(?:M/s\.|M/s|Messrs\.)?\s*([A-Za-z\s&\.]+)\s+(?:has been awarded|has won|wins|awarded to|bags|secures|emerges|selected for)',
        r'([A-Z&]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Limited|Ltd|Corp|Infrastructure|Construction))?)',
        r'([A-Za-z\s&\.]+)-([A-Za-z\s&\.]+)\s+(?:JV|Joint Venture|Consortium)'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, text):
            company = match.group(1).strip()
            # Remove all common prefixes including 'projects.'
            company = re.sub(r'^(?:M/s\.|M/s|Messrs\.|cr\s+|projects\.|Projects\.|project\.|Project\.)\s*', '', company)
            company = re.sub(r'\s+(?:Private|Pvt|Public|Company)\s+(?:Limited|Ltd)$', ' Limited', company)
            company = re.sub(r'\s+(?:Private|Pvt|Public|Company)$', '', company)
            company = re.sub(r'\s+', ' ', company)
            company = company.replace(' and ', ' & ')
            
            if len(company) > 3 and not any(term in company.lower() for term in ['404', 'error', 'not found', 'page']):
                return company
    
    return None

def extract_project_value(text: str) -> Union[float, None]:
    """Extract project value from text."""
    patterns = [
        r'(?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)',
        r'contract value of (?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)',
        r'project value of (?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)',
        r'worth (?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            try:
                value = float(match.group(1).replace(',', ''))
                if 1 <= value <= 100000:  # Validate between 1 crore and 1 lakh crore
                    return value
            except ValueError:
                continue
    
    return None

def determine_product_teams(project: ProjectData) -> list[str]:
    """Determine which product teams should receive the project."""
    text = f"{project.get('title', '')} {project.get('description', '')}".lower()
    steel_reqs = project.get('steel_requirements', {})
    
    # Initialize teams set to avoid duplicates
    teams = set()
    
    # Define comprehensive project type patterns with associated teams
    project_patterns = [
        # Metro/Railway Projects
        {
            'type': 'metro_rail',
            'patterns': ['metro', 'railway', 'rail', 'train', 'locomotive', 'coach', 'rolling stock', 'station', 'terminal', 'depot'],
            'teams': ['HOT_ROLLED', 'COLD_ROLLED', 'TMT_BARS', 'WIRE_RODS']
        },
        # Roads/Highways/Bridges
        {
            'type': 'road_bridge',
            'patterns': ['highway', 'road', 'bridge', 'flyover', 'viaduct', 'corridor', 'expressway', 'underpass', 'overpass'],
            'teams': ['TMT_BARS', 'HOT_ROLLED', 'WIRE_RODS']
        },
        # Buildings/Real Estate
        {
            'type': 'building',
            'patterns': ['building', 'tower', 'complex', 'mall', 'hospital', 'hotel', 'apartment', 'residential', 'commercial', 'office'],
            'teams': ['TMT_BARS', 'GALVANIZED', 'GALVALUME_STEEL']
        },
        # Industrial/Manufacturing
        {
            'type': 'industrial',
            'patterns': ['factory', 'plant', 'manufacturing', 'industrial', 'warehouse', 'storage', 'workshop', 'assembly'],
            'teams': ['HOT_ROLLED', 'COLD_ROLLED', 'GALVANIZED', 'SPECIAL_ALLOY_STEEL']
        },
        # Power/Energy
        {
            'type': 'power',
            'patterns': ['power plant', 'solar', 'renewable', 'wind', 'energy', 'electricity', 'transmission', 'substation', 'grid'],
            'teams': ['SOLAR', 'ELECTRICAL_STEEL', 'GALVANIZED']
        },
        # Water/Irrigation
        {
            'type': 'water',
            'patterns': ['dam', 'reservoir', 'canal', 'pipeline', 'water', 'irrigation', 'treatment', 'sewage'],
            'teams': ['HOT_ROLLED', 'TMT_BARS', 'SPECIAL_ALLOY_STEEL']
        },
        # Defense/Strategic
        {
            'type': 'defense',
            'patterns': ['defense', 'military', 'strategic', 'army', 'navy', 'air force', 'missile', 'ammunition'],
            'teams': ['SPECIAL_ALLOY_STEEL', 'HOT_ROLLED']
        },
        # Ports/Marine
        {
            'type': 'marine',
            'patterns': ['port', 'harbor', 'dock', 'jetty', 'marine', 'coastal', 'shipyard', 'container'],
            'teams': ['HOT_ROLLED', 'GALVANIZED', 'SPECIAL_ALLOY_STEEL']
        }
    ]
    
    # Check for specific steel types mentioned in requirements
    steel_type_teams = {
        'hot rolled': 'HOT_ROLLED',
        'hr': 'HOT_ROLLED',
        'cold rolled': 'COLD_ROLLED',
        'cr': 'COLD_ROLLED',
        'galvanized': 'GALVANIZED',
        'gi': 'GALVANIZED',
        'galvalume': 'GALVALUME_STEEL',
        'gl': 'GALVALUME_STEEL',
        'electrical': 'ELECTRICAL_STEEL',
        'crngo': 'ELECTRICAL_STEEL',
        'crgo': 'ELECTRICAL_STEEL',
        'special': 'SPECIAL_ALLOY_STEEL',
        'alloy': 'SPECIAL_ALLOY_STEEL',
        'wire rod': 'WIRE_RODS',
        'wire': 'WIRE_RODS',
        'tmt': 'TMT_BARS',
        'rebar': 'TMT_BARS',
        'reinforcement': 'TMT_BARS',
        'solar': 'SOLAR',
        'renewable': 'SOLAR'
    }
    
    # Check steel requirements first
    if isinstance(steel_reqs, dict):
        primary_type = steel_reqs.get('primary', {}).get('type', '').lower()
        for steel_term, team in steel_type_teams.items():
            if steel_term in primary_type:
                teams.add(team)
        
        # Check secondary requirements
        secondary_reqs = steel_reqs.get('secondary', [])
        if isinstance(secondary_reqs, list):
            for req in secondary_reqs:
                if isinstance(req, dict):
                    sec_type = req.get('type', '').lower()
                    for steel_term, team in steel_type_teams.items():
                        if steel_term in sec_type:
                            teams.add(team)
    
    # Check project description for steel terms
    for steel_term, team in steel_type_teams.items():
        if steel_term in text:
            teams.add(team)
    
    # Check project patterns
    for pattern_group in project_patterns:
        if any(pattern in text for pattern in pattern_group['patterns']):
            project['project_type'] = pattern_group['type']
            teams.update(pattern_group['teams'])
    
    # If no teams found, check project value for default assignments
    if not teams:
        value = float(project.get('value', 0))
        if value >= 1000:  # Large projects (>1000 crore)
            teams.update(['HOT_ROLLED', 'TMT_BARS', 'GALVANIZED'])
        elif value >= 500:  # Medium projects
            teams.update(['TMT_BARS', 'GALVANIZED'])
        else:  # Small projects
            teams.add('TMT_BARS')
    
    # Convert set to list and ensure at least one team
    teams_list = list(teams)
    if not teams_list:
        teams_list = ['TMT_BARS']  # Default fallback
    
    # Log team assignments
    logger.info(f"Assigned teams {teams_list} to project: {project.get('title')}")
    
    return teams_list

def calculate_priority_score(project: ProjectData) -> int:
    """Calculate priority score for a project."""
    try:
        value = float(project.get('value', 0))
        start_date = project.get('start_date', datetime.now())
        
        # Calculate days until start
        days_until_start = (start_date - datetime.now()).days
        
        # Calculate time factor (higher score for closer start dates)
        time_factor = max(0, 1 - (days_until_start / 365))
        
        # Calculate value factor (higher score for higher values)
        value_factor = min(1, value / 1000)
        
        # Combine factors with weights
        priority_score = (
            time_factor * Config.PRIORITY_WEIGHTS['time_factor'] +
            value_factor * Config.PRIORITY_WEIGHTS['value_factor']
        )
        
        return round(priority_score * 100)
        
    except Exception as e:
        logger.error(f"Error calculating priority score: {str(e)}")
        return 50

def scrape_projects(state: WorkflowState) -> WorkflowState:
    """Scrape projects from various sources."""
    try:
        logger.info("Starting project scraping...")
        
        # Initialize components
        metro_scraper = MetroScraper()
        
        # Get projects from metro scraper
        metro_projects = metro_scraper.scrape_latest_news()
        
        # Extended search queries for more comprehensive results
        search_queries = [
            "new infrastructure project india announced",
            "construction project tender awarded india",
            "infrastructure development project approved india",
            "new metro rail project india",
            "highway construction project india",
            "bridge construction project india",
            "industrial project construction india",
            "steel structure project india",
            "commercial building project india",
            "industrial complex construction india"
        ]
        
        # Get Serper projects
        serper_projects = []
        
        for query in search_queries:
            try:
                # Prepare Serper API request
                payload = json.dumps({
                    "q": query,
                    "num": 10
                })
                headers = {
                    'X-API-KEY': Config.SERPER_API_KEY,
                    'Content-Type': 'application/json'
                }
                
                # Make request to Serper API
                response = requests.post(
                    "https://google.serper.dev/search",
                    headers=headers,
                    data=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    organic_results = data.get('organic', [])
                    
                    for result in organic_results:
                        try:
                            title = result.get('title', '')
                            snippet = result.get('snippet', '')
                            link = result.get('link', '')
                            
                            # Skip if URL is in excluded domains
                            if any(domain in link.lower() for domain in Config.SERPER_SETTINGS['exclude_domains']):
                                continue
                                
                            # Skip if title or snippet is empty
                            if not title or not snippet:
                                continue
                                
                            # Skip if URL is invalid
                            if not link.startswith('http'):
                                continue
                                
                            # Create project from Serper result
                            serper_projects.append({
                                'title': title,
                                'description': snippet,
                                'source_url': link,
                                'source': 'serper_web',
                                'value': 0,  # Will be enriched later
                                'company': '',  # Will be enriched later
                                'start_date': datetime.now(),
                                'end_date': datetime.now() + timedelta(days=365),
                                'news_date': datetime.now()
                            })
                            
                        except Exception as e:
                            logger.warning(f"Failed to process Serper result: {str(e)}")
                            continue
                            
                else:
                    logger.error(f"Serper API returned status code: {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error in Serper search for query '{query}': {str(e)}")
            except Exception as e:
                logger.error(f"Error in Serper search for query '{query}': {str(e)}")
                
            time.sleep(2)  # Add delay between queries
            
        # Combine all projects with deduplication
        seen_urls = set()
        all_projects = []
        
        for project in metro_projects + serper_projects:
            url = project.get('source_url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_projects.append(project)
        
        logger.info(f"Found {len(all_projects)} total projects before filtering")
        logger.info(f"- Metro projects: {len(metro_projects)}")
        logger.info(f"- Serper projects: {len(serper_projects)}")
        
        if not all_projects:
            logger.warning("No projects found from any source")
        
        state['projects'] = all_projects
        state['status'] = 'projects_scraped'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project scraping: {str(e)}"
        state['status'] = 'error'
        return state

def filter_projects(state: WorkflowState) -> WorkflowState:
    """Filter and validate projects."""
    try:
        logger.info(f"Filtering {len(state['projects'])} projects...")
        
        # Get current date for age checking - more lenient timeline
        current_date = datetime.now()
        max_project_age_days = 30  # Increased from 3 to 30 days
        min_date = current_date - timedelta(days=max_project_age_days)

        filtered_projects = []
        jsw_projects = []
        
        # Date extraction patterns
        date_patterns = [
            r'(?:start|begin|commence|initiate)(?:s|ing|ed)?\s+(?:by|from|in|on)?\s+([A-Za-z]+\s+\d{4})',
            r'(?:complete|finish|end|deliver)(?:s|ing|ed)?\s+(?:by|in|on)?\s+([A-Za-z]+\s+\d{4})',
            r'(?:timeline|duration|period|schedule)\s+(?:of|is|:)?\s+(\d+)\s+(?:month|year)s?',
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'([A-Za-z]+\s+\d{4})'
        ]

        for project in state['projects']:
            try:
                # Skip invalid URLs
                if not project.get('source_url'):
                    continue

                # Extract dates from title and description
                text = f"{project.get('title', '')} {project.get('description', '')}"
                
                # Initialize dates
                start_date = None
                end_date = None
                duration_months = None

                # Try to extract dates from text
                for pattern in date_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        try:
                            date_str = match.group(1)
                            
                            # Handle duration pattern
                            if pattern.startswith('(?:timeline|duration'):
                                duration_months = int(date_str)
                                continue
                                
                            # Try different date formats
                            try:
                                # Try MM/DD/YYYY or DD/MM/YYYY
                                if '/' in date_str or '-' in date_str:
                                    date = datetime.strptime(date_str.replace('-', '/'), '%m/%d/%Y')
                                else:
                                    # Try Month YYYY or Month DD, YYYY
                                    try:
                                        date = datetime.strptime(date_str, '%B %Y')
                                    except ValueError:
                                        try:
                                            date = datetime.strptime(date_str, '%B %d, %Y')
                                        except ValueError:
                                            continue
                                
                                if 'start' in match.string.lower() or 'begin' in match.string.lower():
                                    start_date = date
                                elif 'end' in match.string.lower() or 'complete' in match.string.lower():
                                    end_date = date
                                elif not start_date:  # Use as start date if no specific indicator
                                    start_date = date
                                    
                            except ValueError:
                                continue
                                
                        except Exception as e:
                            logger.debug(f"Error parsing date: {str(e)}")
                            continue

                # Set default dates if not found
                if not start_date:
                    start_date = current_date
                
                if not end_date and duration_months:
                    end_date = start_date + timedelta(days=duration_months * 30)
                elif not end_date:
                    end_date = start_date + timedelta(days=365)  # Default 1 year duration

                # Validate timeline logic
                if end_date <= start_date:
                    end_date = start_date + timedelta(days=365)

                # More lenient date filtering - accept projects up to 30 days old
                if start_date < min_date and 'tender' not in text.lower() and 'bid' not in text.lower():
                    logger.info(f"Skipping old project: {project.get('title')} (Start date: {start_date})")
                    continue

                # Skip social media and PDFs
                if any(domain in project['source_url'].lower() for domain in ['facebook.com', 'twitter.com']):
                    continue
                
                # Validate title - more lenient
                title = project.get('title', '').strip()
                if len(title) < 3 or any(term in title.lower() for term in ['404', 'error', 'not found']):
                    continue
                
                # Extract and validate company name early - more lenient
                text = f"{title} {project.get('description', '')}"
                company_name = project.get('company') or extract_company_name(text)
                if not company_name:
                    company_name = "Unknown Company"  # Default company name
                
                # Look for recency indicators - expanded list
                recency_indicators = [
                    'announced', 'launches', 'to build', 'upcoming', 'planned', 
                    'awarded', 'wins', 'secured', 'bags', 'new', 'contract',
                    'project', 'development', 'construction', 'infrastructure',
                    'tender', 'bid', 'proposal', 'approved', 'sanctioned',
                    'investment', 'expansion', 'modernization', 'upgrade'
                ]
                
                # More lenient recency check
                has_relevant_terms = any(indicator in text.lower() for indicator in recency_indicators)
                
                if not has_relevant_terms and start_date < min_date:
                    logger.info(f"Skipping old project without relevance: {title}")
                    continue
                
                # Extract and validate project value - more lenient
                value = project.get('value') or extract_project_value(text)
                if not value:  # Allow zero value projects to pass through
                    value = 0
                project['value'] = value
                
                # Update project with validated data
                project.update({
                    'title': title,
                    'value': value,
                    'company': company_name,
                    'start_date': start_date,
                    'end_date': end_date,
                    'description': project.get('description', '')[:2000],  # Limit description length
                    'is_recent': True  # Mark as recent for prioritization
                })
                
                filtered_projects.append(project)
                
            except Exception as e:
                logger.error(f"Error filtering project: {str(e)}")
                continue
        
        # Sort filtered projects by date (most recent first)
        filtered_projects.sort(key=lambda x: x.get('start_date', datetime.now()), reverse=True)
        
        # Log filtering results
        if jsw_projects:
            logger.info(f"Filtered out {len(jsw_projects)} JSW-related projects")
        
        if not filtered_projects:
            logger.warning("No projects passed filtering stage")
        else:
            logger.info(f"Retained {len(filtered_projects)} projects after filtering")
        
        state['filtered_projects'] = filtered_projects
        state['status'] = 'projects_filtered'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project filtering: {str(e)}"
        state['status'] = 'error'
        return state

def generate_catchy_headline(project: dict) -> str:
    """Generate a catchy headline for a project using Groq."""
    try:
        if not Config.GROQ_API_KEY:
            logger.warning("No Groq API key configured, using original title")
            return project.get('title', '')
            
        try:
            groq_client = Groq(api_key=Config.GROQ_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {str(e)}")
            return project.get('title', '')
            
        # Extract key project details
        title = project.get('title', '')
        company = project.get('company', '')
        description = project.get('description', '')
        steel_requirements = project.get('steel_requirements', {})
        
        # Extract steel quantities
        total_steel = steel_requirements.get('total', 0)
        primary_steel = steel_requirements.get('primary', {}).get('quantity', 0)
        primary_type = steel_requirements.get('primary', {}).get('type', '')
        
        # Prepare context with focus on concrete details
        context = f"""
        Write a concise, factual headline for a construction/infrastructure project lead. Focus on the physical scope and steel requirements.

        Project Details:
        - Company: {company}
        - Original Title: {title}
        - Description: {description}
        - Steel Requirements: {total_steel} MT total, {primary_steel} MT {primary_type}

        Requirements:
        1. Start with the company name
        2. Use action verbs like "wins", "secures", "bags", "to build"
        3. Include the project type (metro, highway, building, etc.)
        4. Include location if mentioned
        5. Include key numbers (length, units, capacity) if available
        6. Keep it under 10 words
        7. Do NOT mention monetary values
        8. Do NOT use buzzwords or marketing language
        9. Focus on facts, not speculation

        Example Headlines:
        * L&T to build 65-km Patna highway section
        * Afcons wins Delhi metro contract for 12 stations
        * Tata Projects secures Mumbai-Ahmedabad rail package
        * MEIL to construct 200-km irrigation canal in Andhra
        
        Return ONLY the headline, no extra text.
        """
        
        try:
            completion = groq_client.chat.completions.create(
                messages=[{
                    "role": "system",
                    "content": "You are a headline writer for infrastructure projects. Write clear, factual headlines that focus on project scope and steel requirements."
                }, {
                    "role": "user",
                    "content": context
                }],
                model="llama-3.3-70b-versatile",  # Using a more capable model
                temperature=0.1,  # Lower temperature for more consistent output
                max_tokens=50  # Shorter output for headlines
            )
            
            headline = completion.choices[0].message.content.strip()
            
            # Clean up the headline
            headline = headline.replace('"', '').replace("'", "")
            headline = re.sub(r'\s+', ' ', headline).strip()
            headline = re.sub(r'\(.*?\)', '', headline).strip()  # Remove parenthetical text
            headline = re.sub(r'(?i)\b(ltd|limited|corp|corporation)\b', '', headline).strip()  # Remove company suffixes
            
            # Remove any headers or extra lines
            headline = headline.split('\n')[-1].strip()
            
            # Ensure it's not too long
            if len(headline) > 80:
                headline = headline[:77] + "..."
                
            return headline
            
        except Exception as e:
            logger.error(f"Error generating headline with Groq: {str(e)}")
            return project.get('title', '')  # Fallback to original title
            
    except Exception as e:
        logger.error(f"Error in headline generation: {str(e)}")
        return project.get('title', '')  # Fallback to original title

def extract_location(text: str) -> str:
    """Extract location from project description."""
    # List of major Indian states and cities
    locations = [
        'Delhi', 'Mumbai', 'Kolkata', 'Chennai', 'Bangalore', 'Hyderabad', 'Ahmedabad',
        'Pune', 'Surat', 'Jaipur', 'Lucknow', 'Kanpur', 'Nagpur', 'Indore', 'Thane',
        'Bhopal', 'Visakhapatnam', 'Patna', 'Vadodara', 'Ghaziabad', 'Ludhiana',
        'Agra', 'Nashik', 'Faridabad', 'Meerut', 'Rajkot', 'Varanasi', 'Srinagar',
        'Aurangabad', 'Dhanbad', 'Amritsar', 'Navi Mumbai', 'Allahabad', 'Ranchi',
        'Howrah', 'Coimbatore', 'Jabalpur', 'Gwalior', 'Vijayawada', 'Jodhpur',
        'Madurai', 'Raipur', 'Kota', 'Chandigarh', 'Guwahati', 'Solapur', 'Hubli',
        'Dharwad', 'Bareilly', 'Moradabad', 'Mysore', 'Gurgaon', 'Aligarh', 'Jalandhar',
        'Maharashtra', 'Gujarat', 'Rajasthan', 'Karnataka', 'Andhra Pradesh', 'Tamil Nadu',
        'Uttar Pradesh', 'West Bengal', 'Bihar', 'Madhya Pradesh', 'Telangana', 'Odisha',
        'Kerala', 'Assam', 'Punjab', 'Haryana', 'Jammu and Kashmir', 'Uttarakhand',
        'Himachal Pradesh', 'Tripura', 'Meghalaya', 'Manipur', 'Nagaland', 'Goa',
        'Arunachal Pradesh', 'Mizoram', 'Sikkim'
    ]
    
    # Find all locations mentioned in the text
    found_locations = []
    for location in locations:
        if location.lower() in text.lower():
            found_locations.append(location)
    
    if found_locations:
        return found_locations[0]  # Return the first location found
    return 'India'  # Default to India if no specific location found

def enrich_projects(state: WorkflowState) -> WorkflowState:
    """Enrich projects with steel requirements, team assignments, and contact information."""
    try:
        logger.info(f"Enriching {len(state['filtered_projects'])} projects...")
        
        email_handler = EmailHandler()
        contact_finder = ContactFinder()  # Initialize contact finder
        enriched_projects = []
        max_retries = 3
        
        # Track statistics
        total_projects = len(state['filtered_projects'])
        jsw_filtered = 0
        enrichment_failed = 0
        successfully_enriched = 0

        def extract_company_domain(url):
            """Extract company domain from URL"""
            try:
                parsed = urlparse(url)
                # Get the domain without www.
                domain = parsed.netloc.replace('www.', '')
                return domain
            except Exception as e:
                logger.error(f"Error extracting domain: {str(e)}")
                return None

        # JSW product terms to filter out
        jsw_product_terms = [
            'jsw neosteel', 'jsw steel', 'jsw trusteel', 'neosteel', 'trusteel',
            'jsw fastbuild', 'jsw galvalume', 'jsw colour coated', 'jsw coated',
            'jsw gi', 'jsw hr', 'jsw cr', 'jsw tmt', 'jsw electrical steel',
            'jsw special steel', 'jsw plates', 'neosteel 550d', 'neosteel 600',
            'neosteel eds', 'neosteel crs', 'neosteel fastbuild', 'neostrands pc',
            'trusteel plates'
        ]
        
        for project in state['filtered_projects']:
            for retry in range(max_retries):
                try:
                    # Convert project to dictionary if it's not already
                    if not isinstance(project, dict):
                        if isinstance(project, str):
                            project = {
                                'title': project,
                                'description': project,
                                'value': 0,
                                'company': '',
                                'source_url': '',
                                'start_date': datetime.now(),
                                'end_date': datetime.now() + timedelta(days=365)
                            }
                        elif isinstance(project, list):
                            # If it's a list, try to convert first element to title
                            project = {
                                'title': str(project[0]) if project else '',
                                'description': ' '.join(str(x) for x in project),
                                'value': 0,
                                'company': '',
                                'source_url': '',
                                'start_date': datetime.now(),
                                'end_date': datetime.now() + timedelta(days=365)
                            }
                        else:
                            logger.warning(f"Skipping project of unknown type: {type(project)}")
                            enrichment_failed += 1
                            break

                    # Ensure required fields exist
                    project.setdefault('title', '')
                    project.setdefault('description', '')
                    project.setdefault('value', 0)
                    project.setdefault('company', '')
                    project.setdefault('source_url', '')
                    project.setdefault('start_date', datetime.now())
                    project.setdefault('end_date', datetime.now() + timedelta(days=365))
                    
                    # Extract project type and specifications
                    title = project['title'].lower()
                    description = project['description'].lower()
                    full_text = f"{title} {description}"
                    
                    # Determine project type
                    project_type = 'infrastructure'  # default
                    if any(term in full_text for term in ['metro', 'railway', 'rail']):
                        project_type = 'metro'
                    elif any(term in full_text for term in ['high rise', 'building', 'residential', 'commercial']):
                        project_type = 'high_rise'
                    elif any(term in full_text for term in ['industrial', 'factory', 'plant', 'manufacturing']):
                        project_type = 'industrial'
                    
                    # Extract specifications
                    specs = {
                        'length': None,
                        'area': None,
                        'capacity': None,
                        'floors': None
                    }
                    
                    # Try to extract length (for infrastructure projects)
                    length_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:km|kilometer)', full_text)
                    if length_matches:
                        specs['length'] = float(length_matches[0])
                    
                    # Try to extract area
                    area_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:sq\.?\s*(?:ft|meter|m)|sqft)', full_text)
                    if area_matches:
                        specs['area'] = float(area_matches[0])
                    
                    # Try to extract number of floors
                    floor_matches = re.findall(r'(\d+)\s*(?:floor|storey)', full_text)
                    if floor_matches:
                        specs['floors'] = int(floor_matches[0])
                    
                    # Calculate steel requirements
                    value_in_cr = project.get('value', 0)
                    base_steel_mt = value_in_cr * 100  # Rough estimate: 100 MT per crore
                    
                    steel_reqs = {
                        'primary': {'type': 'TMT Bars', 'quantity': 0},
                        'secondary': [
                            {'type': 'Hot Rolled', 'quantity': 0},
                            {'type': 'Cold Rolled', 'quantity': 0}
                        ],
                        'tertiary': {'type': 'Wire Rods', 'quantity': 0}
                    }
                    
                    if project_type == 'metro':
                        steel_reqs['primary']['type'] = 'Hot Rolled'
                        steel_reqs['primary']['quantity'] = int(base_steel_mt * 0.4)
                        steel_reqs['secondary'][0]['quantity'] = int(base_steel_mt * 0.3)
                        steel_reqs['secondary'][1]['quantity'] = int(base_steel_mt * 0.2)
                        steel_reqs['tertiary']['quantity'] = int(base_steel_mt * 0.1)
                    elif project_type == 'high_rise':
                        steel_reqs['primary']['type'] = 'TMT Bars'
                        steel_reqs['primary']['quantity'] = int(base_steel_mt * 0.5)
                        steel_reqs['secondary'][0]['quantity'] = int(base_steel_mt * 0.2)
                        steel_reqs['secondary'][1]['quantity'] = int(base_steel_mt * 0.2)
                        steel_reqs['tertiary']['quantity'] = int(base_steel_mt * 0.1)
                    elif project_type == 'industrial':
                        steel_reqs['primary']['type'] = 'Hot Rolled'
                        steel_reqs['primary']['quantity'] = int(base_steel_mt * 0.35)
                        steel_reqs['secondary'][0]['quantity'] = int(base_steel_mt * 0.35)
                        steel_reqs['secondary'][1]['quantity'] = int(base_steel_mt * 0.2)
                        steel_reqs['tertiary']['quantity'] = int(base_steel_mt * 0.1)
                    else:  # Default infrastructure
                        steel_reqs['primary']['type'] = 'TMT Bars'
                        steel_reqs['primary']['quantity'] = int(base_steel_mt * 0.4)
                        steel_reqs['secondary'][0]['quantity'] = int(base_steel_mt * 0.3)
                        steel_reqs['secondary'][1]['quantity'] = int(base_steel_mt * 0.2)
                        steel_reqs['tertiary']['quantity'] = int(base_steel_mt * 0.1)
                    
                    # Adjust based on specifications if available
                    if specs['length']:
                        # For infrastructure projects with length, adjust based on length
                        length_factor = min(specs['length'] / 10, 2.0)  # Cap at 2x for very long projects
                        for req in [steel_reqs['primary']] + steel_reqs['secondary'] + [steel_reqs['tertiary']]:
                            req['quantity'] = int(req['quantity'] * length_factor)
                    elif specs['area']:
                        # For building projects with area, adjust based on area
                        area_factor = min(specs['area'] / 10000, 2.0)  # Cap at 2x for very large areas
                        for req in [steel_reqs['primary']] + steel_reqs['secondary'] + [steel_reqs['tertiary']]:
                            req['quantity'] = int(req['quantity'] * area_factor)
                    elif specs['floors']:
                        # For high-rise projects with floors, adjust based on number of floors
                        floor_factor = min(specs['floors'] / 20, 2.0)  # Cap at 2x for very tall buildings
                        for req in [steel_reqs['primary']] + steel_reqs['secondary'] + [steel_reqs['tertiary']]:
                            req['quantity'] = int(req['quantity'] * floor_factor)
                    
                    # Calculate total steel requirement
                    steel_reqs['total'] = (
                        steel_reqs['primary']['quantity'] +
                        sum(req['quantity'] for req in steel_reqs['secondary']) +
                        steel_reqs['tertiary']['quantity']
                    )
                    
                    # Set minimum quantities
                    min_quantity = 50  # Minimum 50 MT for any requirement
                    steel_reqs['primary']['quantity'] = max(steel_reqs['primary']['quantity'], min_quantity)
                    for sec_req in steel_reqs['secondary']:
                        sec_req['quantity'] = max(sec_req['quantity'], min_quantity)
                    steel_reqs['tertiary']['quantity'] = max(steel_reqs['tertiary']['quantity'], min_quantity)
                    
                    # Update project with enriched data
                    project['project_type'] = project_type
                    project['specifications'] = specs
                    project['steel_requirements'] = steel_reqs
                    
                    # Extract company website domain from source URL
                    if project.get('source_url'):
                        company_domain = extract_company_domain(project['source_url'])
                        if company_domain:
                            project['company_website'] = f"https://{company_domain}"
                    
                    # Double check for JSW terms in enriched content
                    all_text = f"{project.get('title', '')} {project.get('description', '')} {str(project.get('steel_requirements', ''))}".lower()
                    if any(term in all_text for term in jsw_product_terms):
                        logger.info(f"Filtered JSW-related project during enrichment: {project.get('company')} - {project.get('title')}")
                        jsw_filtered += 1
                        break
                    
                    # Find procurement contacts
                    try:
                        project = contact_finder.enrich_project_contacts(project)
                    except Exception as e:
                        logger.error(f"Error finding contacts: {str(e)}")
                        # Add default contact info
                        project.setdefault('contacts', [{
                            'name': 'Procurement Team',
                            'role': 'Procurement Department',
                            'email': 'procurement@company.com',
                            'phone': 'N/A'
                        }])
                    
                    enriched_projects.append(project)
                    successfully_enriched += 1
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if retry == max_retries - 1:  # Last retry
                        logger.error(f"Error enriching project after {max_retries} retries: {str(e)}")
                        enrichment_failed += 1
                    time.sleep(1)  # Wait before retry
                    continue
        
        # Log detailed statistics
        logger.info(f"Enrichment statistics:")
        logger.info(f"- Total projects processed: {total_projects}")
        logger.info(f"- Successfully enriched: {successfully_enriched}")
        logger.info(f"- JSW-related filtered: {jsw_filtered}")
        logger.info(f"- Enrichment failed: {enrichment_failed}")
        
        if not enriched_projects:
            logger.warning("No projects were successfully enriched")
            
        logger.info(f"Successfully enriched {len(enriched_projects)} projects")
        state['enriched_projects'] = enriched_projects
        state['status'] = 'projects_enriched'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project enrichment: {str(e)}"
        state['status'] = 'error'
        return state

def prioritize_projects(state: WorkflowState) -> WorkflowState:
    """Prioritize and sort projects."""
    try:
        logger.info(f"Prioritizing {len(state['enriched_projects'])} projects...")
        
        # Validate and normalize priority scores
        for project in state['enriched_projects']:
            try:
                score = project.get('priority_score', 0)
                if score < 0 or score > 100:
                    # Recalculate score if invalid
                    score = calculate_priority_score(project)
                project['priority_score'] = score
                
                # Add urgency tag based on timeline
                start_date = project.get('start_date', datetime.now())
                days_until_start = (start_date - datetime.now()).days
                
                if days_until_start <= 90:  # 3 months
                    project['tags'] = ['Urgent Priority']
                elif days_until_start <= 180:  # 6 months
                    project['tags'] = ['High Priority']
                else:
                    project['tags'] = ['Normal Priority']
                
                # Add value tag
                value = project.get('value', 0)
                if value >= 1000:
                    project['tags'].append('Major Project')
                elif value >= 500:
                    project['tags'].append('Large Project')
                
                # Add steel requirement tag
                steel_req = project.get('steel_requirements', {}).get('total', 0)
                if steel_req >= 10000:
                    project['tags'].append('High Steel Requirement')
                
            except Exception as e:
                logger.error(f"Error processing project tags: {str(e)}")
                project['tags'] = ['Normal Priority']
                continue
        
        # Sort projects by priority score
        prioritized_projects = sorted(
            state['enriched_projects'],
            key=lambda x: (
                x.get('priority_score', 0),
                x.get('value', 0),
                x.get('steel_requirements', {}).get('total', 0)
            ),
            reverse=True
        )
        
        # Log prioritization results
        logger.info(f"Successfully prioritized {len(prioritized_projects)} projects")
        
        # Store all prioritized projects without any limits
        state['prioritized_projects'] = prioritized_projects
        state['status'] = 'projects_prioritized'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project prioritization: {str(e)}"
        state['status'] = 'error'
        return state

def send_notifications(state: WorkflowState) -> WorkflowState:
    """Send notifications about discovered projects."""
    try:
        logger.info("Sending notifications...")
        
        if not state.get('prioritized_projects'):
            logger.warning("No projects to send notifications for")
            state['status'] = 'completed'
            return state
            
        # Initialize notification handlers
        email_handler = EmailHandler()
        whatsapp_handler = InteraktHandler()
        
        # Send email notifications
        email_success = email_handler.send_project_opportunities(state['prioritized_projects'])
        if not email_success:
            logger.error("Failed to send email notifications")
            
        # Send WhatsApp notifications
        whatsapp_success = whatsapp_handler.send_project_opportunities(state['prioritized_projects'])
        if not whatsapp_success:
            logger.error("Failed to send WhatsApp notifications")
            
        if email_success or whatsapp_success:
            state['status'] = 'completed'
        else:
            state['status'] = 'notification_failed'
            state['error'] = "Failed to send notifications"
            
        return state
        
    except Exception as e:
        logger.error(f"Error sending notifications: {str(e)}")
        state['error'] = f"Error in notifications: {str(e)}"
        state['status'] = 'error'
        return state

def create_workflow() -> Graph:
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("scrape_projects", scrape_projects)
    workflow.add_node("filter_projects", filter_projects)
    workflow.add_node("enrich_projects", enrich_projects)
    workflow.add_node("prioritize_projects", prioritize_projects)
    workflow.add_node("send_notifications", send_notifications)
    
    # Add edges
    workflow.add_edge("scrape_projects", "filter_projects")
    workflow.add_edge("filter_projects", "enrich_projects")
    workflow.add_edge("enrich_projects", "prioritize_projects")
    workflow.add_edge("prioritize_projects", "send_notifications")
    
    # Set entry point
    workflow.set_entry_point("scrape_projects")
    
    # Compile workflow
    return workflow.compile()

def run_workflow() -> dict:
    """Run the project discovery workflow."""
    try:
        # Initialize workflow
        workflow = create_workflow()
        
        # Initialize state with empty lists and status tracking
        initial_state = WorkflowState(
            projects=[],
            filtered_projects=[],
            enriched_projects=[],
            prioritized_projects=[],
            error=None,
            status='initialized'
        )
        
        # Track timing for monitoring
        start_time = datetime.now()
        
        # Run workflow with timing for each step
        final_state = workflow.invoke(initial_state)
        step_time = datetime.now() - start_time
        logger.info(f"Workflow completed in {step_time.total_seconds():.2f}s")
        
        # Log final statistics
        logger.info(f"Workflow completed with status: {final_state['status']}")
        logger.info(f"Projects found: {len(final_state.get('projects', []))}")
        logger.info(f"Projects filtered: {len(final_state.get('filtered_projects', []))}")
        logger.info(f"Projects enriched: {len(final_state.get('enriched_projects', []))}")
        logger.info(f"Projects prioritized: {len(final_state.get('prioritized_projects', []))}")
        
        return final_state
        
    except Exception as e:
        logger.error(f"Workflow error: {str(e)}")
        return {
            'error': str(e),
            'status': 'error',
            'projects': [],
            'filtered_projects': [],
            'enriched_projects': [],
            'prioritized_projects': []
        } 