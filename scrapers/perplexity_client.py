import requests # type: ignore
import json
import logging
from config.settings import Config
from datetime import datetime, timedelta
import re
import time

class PerplexityClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {Config.PERPLEXITY_API_KEY}',
            'Content-Type': 'application/json'
        })
    
    def research_infrastructure_projects(self):
        """Research latest infrastructure project news"""
        projects = []
        
        # Primary query focusing on recent contract awards
        primary_query = """
        Search for the latest infrastructure contract wins by companies in India only, particularly in sectors such as construction, transportation, energy, and urban development, rail, metro. Strictly exclude any news or contracts from abroad.

        Check these specific websites for contract wins news:
        - https://www.biddetail.com/procurement-news/epc-contract
        - https://newsonprojects.com
        - https://constructionopportunities.in/
        - https://projectxindia.com
        - https://metrorailtoday.com
        - https://themetrorailguy.com
        - https://www.projectstoday.com
        - https://www.biltrax.com

        Monitor these priority companies:
        - Dilip Buildcon
        - Larsen & Toubro (L&T) and its various arms (L&T Construction, etc.)
        - PNC Infratech
        - HG Infra Engineering
        - IRB Infrastructure Trust
        - Cube Highways and Infrastructure
        - GR Infraprojects
        - Afcons Infrastructure
        - Rail Vikas Nigam Limited (RVNL)
        - J Kumar Infraprojects
        - Megha Engineering and Infrastructure (MEIL)
        - Ashoka Buildcon
        - Torrent Power
        - Genus Power Infrastructure
        - Patel Engineering
        - NHAI (National Highways Authority of India)
        - NHSRCL (National High-Speed Rail Corporation Limited)
        - MSRDC (Maharashtra State Road Development Corporation)
        - RSIIL (Roadway Solutions India Infra Limited)
        - Madhaav Infra Projects

        Format each project as:
        Company: [Company Name]
        Title: [Project Title]
        Value: [Value in Crores]
        Location: [Project Location]
        Timeline: [Start Date - End Date]
        Steel Requirement: [Quantity in MT]
        Description: [Full article text]
        Source: [Complete https:// URL]

        Focus on:
        1. Contract awards in the last day with possible steel requirements
        2. New project announcements with steel procurement needs
        3. Priority projects including:
           - Road/rail infrastructure
           - Metro rail projects
           - Commercial and residential real estate
           - Port developments

        Auto-filter criteria:
        - Projects above 20 lakhs in value
        - Only Indian news
        - Relevant to steel supply

        JSW-specific criteria:
        - Projects requiring TMT Bars
        - Projects needing HR Plates
        - HSLA requirements
        - Coated products demand
        - Solar-specific steel needs

        High-priority opportunities:
        - Large-scale infrastructure (>100 crore)
        - Significant steel requirement (>1000 MT)
        - Urgent timeline (starting within 6 months)
        """
        
        try:
            self.logger.info("Searching for infrastructure projects...")
            results = self._query_perplexity(primary_query)
            projects.extend(self._parse_project_results(results))
            
            # Log results
            self.logger.info(f"Found {len(projects)} projects")
            
            if not projects:
                self.logger.warning("No projects found")
            
            return projects
            
        except Exception as e:
            self.logger.error(f"Error researching projects: {str(e)}", exc_info=True)
            return []
    
    def _query_perplexity(self, query):
        """Make API call to Perplexity with retries"""
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    'https://api.perplexity.ai/chat/completions',
                    json={
                        'model': 'sonar-pro',
                        'messages': [
                            {
                                'role': 'system',
                                'content': 'You are a specialized infrastructure research assistant. Always perform thorough web searches to find the most recent project information. Return ONLY verified information from reliable sources. Format each project exactly as specified.'
                            },
                            {
                                'role': 'user',
                                'content': query
                            }
                        ],
                        'temperature': 0.1,  # Lower temperature for more focused results
                        'max_tokens': 2000,
                        'top_p': 0.9,
                        'web_search': True
                    },
                    timeout=30  # Add timeout
                )
                
                response.raise_for_status()
                response_data = response.json()
                
                if 'choices' in response_data and response_data['choices']:
                    content = response_data['choices'][0]['message']['content']
                    self.logger.debug(f"API Response Content (first 500 chars): {content[:500]}")
                    return response_data
                else:
                    raise Exception("No choices in API response")
                    
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
        
        raise Exception(f"All retries failed. Last error: {last_error}")

    def _parse_project_results(self, results):
        """Parse project information from API response"""
        projects = []
        try:
            if not results or 'choices' not in results or not results['choices']:
                return projects
                
            content = results['choices'][0]['message']['content']
            
            # Split into project blocks using stronger delimiters
            project_blocks = re.split(r'\n\s*(?=Company:|Source:https://)', content)
            
            for block in project_blocks:
                if not block.strip():
                    continue
                    
                try:
                    project = {
                        'news_date': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'perplexity'
                    }
                    
                    # Extract company name
                    if company_match := re.search(r'Company:\s*([^\n]+)', block):
                        project['company'] = company_match.group(1).strip()
                    
                    # Extract project title
                    if title_match := re.search(r'Title:\s*([^\n]+)', block):
                        project['title'] = title_match.group(1).strip()
                    
                    # Extract value (handle crore/lakh formats)
                    if value_match := re.search(r'Value:\s*(?:Rs\.)?\s*(\d+(?:\.\d+)?)\s*(Crores?|Lakhs?|Cr)', block, re.IGNORECASE):
                        value = float(value_match.group(1))
                        unit = value_match.group(2).lower()
                        if 'lakh' in unit:
                            value = value / 100  # Convert to crores
                        project['value'] = value
                    
                    # Extract location
                    if location_match := re.search(r'Location:\s*([^\n]+)', block):
                        project['location'] = location_match.group(1).strip()
                    
                    # Enhanced timeline extraction
                    if timeline_match := re.search(r'Timeline:\s*([^\n]+)', block):
                        timeline = timeline_match.group(1).strip()
                        
                        # Try different timeline formats
                        try:
                            # Format: "Month Year - Month Year"
                            if ' - ' in timeline:
                                start_str, end_str = timeline.split(' - ')
                                project['start_date'] = datetime.strptime(start_str.strip(), '%B %Y')
                                project['end_date'] = datetime.strptime(end_str.strip(), '%B %Y')
                            
                            # Format: "X months" or "X years"
                            elif duration_match := re.search(r'(\d+)\s*(month|year)s?', timeline, re.IGNORECASE):
                                duration = int(duration_match.group(1))
                                unit = duration_match.group(2).lower()
                                
                                project['start_date'] = datetime.now()
                                if 'year' in unit:
                                    duration *= 12
                                project['end_date'] = project['start_date'] + timedelta(days=duration * 30)
                            
                            # Format: "Expected completion by Month Year"
                            elif completion_match := re.search(r'(?:completion|complete|end)\s+by\s+([A-Za-z]+\s+\d{4})', timeline, re.IGNORECASE):
                                end_date = datetime.strptime(completion_match.group(1), '%B %Y')
                                project['start_date'] = datetime.now()
                                project['end_date'] = end_date
                            
                            # Format: "Starting from Month Year"
                            elif start_match := re.search(r'(?:start|begin|commence)\s+(?:from|in|by)?\s+([A-Za-z]+\s+\d{4})', timeline, re.IGNORECASE):
                                start_date = datetime.strptime(start_match.group(1), '%B %Y')
                                project['start_date'] = start_date
                                project['end_date'] = start_date + timedelta(days=730)  # Default 24 months
                            
                            # Default case: use current date and add default duration
                            else:
                                project['start_date'] = datetime.now()
                                project['end_date'] = project['start_date'] + timedelta(days=730)  # Default 24 months
                                
                        except ValueError as ve:
                            self.logger.debug(f"Timeline parsing detail: {str(ve)}")
                            # Set default dates if parsing fails
                            project['start_date'] = datetime.now()
                            project['end_date'] = project['start_date'] + timedelta(days=730)
                    
                    # Extract steel requirement
                    if steel_match := re.search(r'Steel Requirement:\s*(\d+(?:\.\d+)?)\s*(?:MT|Tonnes?)', block, re.IGNORECASE):
                        project['steel_requirement'] = round(float(steel_match.group(1)))
                        project['steel_requirement_display'] = f"~{project['steel_requirement']:,} MT"
                    
                    # Extract full article text
                    if desc_match := re.search(r'Description:\s*([^\n]*(?:\n(?!Source:)[^\n]+)*)', block):
                        project['description'] = desc_match.group(1).strip()
                    
                    # Extract complete source URL
                    if source_match := re.search(r'Source:\s*(https?://[^\s\n]+)', block):
                        project['source_url'] = source_match.group(1).strip()
                    
                    # Add steel demand estimation
                    if (project.get('company') and project.get('title') and 
                        project.get('source_url') and project.get('description') and
                        (project.get('value', 0) >= 0.2 or project.get('steel_requirement', 0) > 0)):
                        project['steel_demand'] = self._estimate_steel_demand(project)
                        if project.get('steel_requirement'):
                            project['steel_requirement'] = round(project['steel_requirement'])
                            project['steel_requirement_display'] = f"~{project['steel_requirement']:,} MT"
                        projects.append(project)
                        
                except Exception as e:
                    self.logger.error(f"Error parsing block: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully parsed {len(projects)} projects")
            
        except Exception as e:
            self.logger.error(f"Error parsing results: {str(e)}")
        
        return projects

    def _get_procurement_team_info(self, company, project_title):
        """Get procurement team information for a specific company/project"""
        query = f"""
        Find information about the procurement team and key decision makers at {company} 
        who would be involved in steel procurement for the project: {project_title}
        
        Focus on:
        1. Head of Procurement/Materials
        2. Project Director/Manager
        3. Any other key decision makers
        
        Include their:
        - Name
        - Role/Position
        - Contact information (if publicly available)
        """
        
        try:
            results = self._query_perplexity(query)
            return self._parse_procurement_results(results)
        except Exception as e:
            self.logger.error(f"Error getting procurement team info: {str(e)}")
            return None

    def _parse_procurement_results(self, results):
        """Parse procurement team information"""
        try:
            content = results['choices'][0]['message']['content']
            
            procurement_info = {
                'key_contacts': [],
                'department_info': '',
                'recent_updates': ''
            }
            
            # Extract contact information
            contact_pattern = r'(?:^|\n)(?:[-•*]\s*)?([^:\n]+):\s*([^\n]+)(?:\n(?:[-•*]\s*)?(?:Contact|Email|Phone):\s*([^\n]+))?'
            contacts = re.finditer(contact_pattern, content, re.MULTILINE)
            
            for match in contacts:
                name = match.group(1).strip()
                role = match.group(2).strip()
                contact = match.group(3).strip() if match.group(3) else None
                
                if name and role:
                    procurement_info['key_contacts'].append({
                        'name': name,
                        'role': role,
                        'contact': contact
                    })
            
            return procurement_info
            
        except Exception as e:
            self.logger.error(f"Error parsing procurement results: {str(e)}")
            return None

    def _estimate_steel_requirement(self, description, project_value):
        """Estimate steel requirement based on project type and value"""
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

    def _estimate_steel_demand(self, project):
        """Estimate steel demand for primary and secondary products based on project details"""
        try:
            # Step 1: Extract Project Data
            description = project.get('description', '').lower()
            title = project.get('title', '').lower()
            value = project.get('value', 0)  # in crores
            
            # Identify industry and sub-sector
            industry = None
            sub_sector = None
            
            # Infrastructure checks
            if any(word in description + title for word in ['highway', 'road', 'bridge', 'flyover']):
                industry = 'infrastructure'
                sub_sector = 'highways' if 'highway' in description + title else 'bridges'
            elif any(word in description + title for word in ['railway', 'rail', 'track']):
                industry = 'infrastructure'
                sub_sector = 'railways'
            elif any(word in description + title for word in ['metro', 'rapid transit']):
                industry = 'infrastructure'
                sub_sector = 'metro'
            elif any(word in description + title for word in ['port', 'harbor', 'dock']):
                industry = 'infrastructure'
                sub_sector = 'ports'
            elif any(word in description + title for word in ['smart city', 'urban development']):
                industry = 'infrastructure'
                sub_sector = 'smart_cities'
            
            # Construction checks
            elif any(word in description + title for word in ['residential', 'housing', 'apartment']):
                industry = 'construction'
                sub_sector = 'residential'
            elif any(word in description + title for word in ['commercial', 'office', 'mall']):
                industry = 'construction'
                sub_sector = 'commercial'
            elif any(word in description + title for word in ['factory', 'plant', 'industrial']):
                industry = 'construction'
                sub_sector = 'industrial'
            
            # Renewable checks
            elif any(word in description + title for word in ['solar', 'pv', 'photovoltaic']):
                industry = 'renewable'
                sub_sector = 'solar'
            elif any(word in description + title for word in ['wind', 'turbine']):
                industry = 'renewable'
                sub_sector = 'wind'
            elif any(word in description + title for word in ['hydro', 'dam']):
                industry = 'renewable'
                sub_sector = 'hydro'
            
            # Industrial checks
            elif any(word in description + title for word in ['machinery', 'equipment']):
                industry = 'industrial'
                sub_sector = 'machinery' if 'machinery' in description + title else 'equipment'
            
            # Default to infrastructure if no clear match
            if not industry:
                industry = 'infrastructure'
                sub_sector = 'highways'
            
            # Step 2: Map to Products
            products = Config.PRODUCT_MAPPING.get(industry, {}).get(sub_sector, {
                'primary': 'TMT_BARS',
                'secondary': 'HR_PLATES'
            })
            
            # Step 3: Estimate Quantities
            def calculate_tonnage(product_type, sub_sector):
                base_rate = Config.STEEL_RATES.get(product_type, {}).get(sub_sector, 
                    Config.STEEL_RATES.get(product_type, {}).get('default', 10))
                return round(base_rate * value * 0.8)  # Apply 0.8 conservative factor
            
            primary_product = products['primary']
            secondary_product = products['secondary']
            
            primary_tonnage = calculate_tonnage(primary_product, sub_sector)
            secondary_tonnage = calculate_tonnage(secondary_product, sub_sector)
            
            # Format the output string with rounded numbers and ~ symbol
            output = f"Primary Product: {primary_product.replace('_', ' ')}: ~{primary_tonnage:,}MT\n"
            output += f"Secondary Product: {secondary_product.replace('_', ' ')}: ~{secondary_tonnage:,}MT"
            
            return output
            
        except Exception as e:
            self.logger.error(f"Error estimating steel demand: {str(e)}")
            return "Could not estimate steel demand due to insufficient data"

    def get_project_info(self, project_context):
        """Get detailed project information based on context and user query"""
        try:
            # Prepare system message for project-specific context
            system_message = """You are a specialized project assistant for JSW Steel. You have deep knowledge about:
            1. Infrastructure and construction projects in India
            2. Steel requirements and specifications for different project types
            3. Project timelines and milestones
            4. Key stakeholders and procurement processes
            5. Market trends and competitive analysis
            
            Provide detailed, accurate responses based on the project context provided.
            If you're not sure about something, acknowledge it and suggest where to find that information.
            Keep responses concise but informative."""
            
            response = self.session.post(
                'https://api.perplexity.ai/chat/completions',
                json={
                    'model': 'sonar-pro',
                    'messages': [
                        {
                            'role': 'system',
                            'content': system_message
                        },
                        {
                            'role': 'user',
                            'content': project_context
                        }
                    ],
                    'temperature': 0.3,  # Lower temperature for more focused responses
                    'max_tokens': 1000,
                    'top_p': 0.9,
                    'web_search': True
                },
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            if 'choices' in response_data and response_data['choices']:
                return response_data['choices'][0]['message']['content']
            else:
                raise Exception("No response from Perplexity API")
                
        except Exception as e:
            self.logger.error(f"Error getting project info: {str(e)}")
            return "I apologize, but I encountered an error while retrieving that information. Please try asking in a different way or contact support for assistance." 