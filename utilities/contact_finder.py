"""Contact finder utility for project contacts."""

import logging
from typing import Dict, List, Optional
import re
from groq import Groq
import os
from dotenv import load_dotenv
import json

logger = logging.getLogger(__name__)
load_dotenv()

class ContactFinder:
    def __init__(self):
        """Initialize contact finder."""
        try:
            self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {str(e)}")
            self.groq_client = None
        self.logger = logging.getLogger(__name__)
        # Initialize static CRM data
        self.crm_data = {
            'nhai': {
                'contacts': [
                    {
                        'name': 'Rajat Mehta',
                        'email': 'rajath.mehta@nhai.gov.in',
                        'phone': '+91-9876543210',
                        'role': 'Chief Procurement Officer',
                        'notes': 'Led procurement for the Delhi-Mumbai Expressway; collaborated with Larsen & Toubro for geosynthetic materials'
                    },
                    {
                        'name': 'Ananya Reddy',
                        'email': 'ananya.reddy@nhai.gov.in',
                        'phone': '+91-8765432109',
                        'role': 'Head of Procurement'
                    }
                ]
            },
            'msrfc': {
                'contacts': [
                    {
                        'name': 'Vikram Singhania',
                        'email': 'vikram.singhania@msrfc.com',
                        'phone': '+91-9988776655',
                        'role': 'Director of Procurement',
                        'notes': 'Partnered with Tata Steel for structural components in the Chennai Port expansion'
                    },
                    {
                        'name': 'Priya Khurana',
                        'email': 'priya.khurana@msrfc.com',
                        'phone': '+91-8877665544',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'kec international': {
                'contacts': [
                    {
                        'name': 'Vivek Sharma',
                        'email': 'vivek.sharma@kec.com',
                        'phone': '+91-9876543320',
                        'role': 'Director of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Nikhil Kapoor for transmission tower steel in the Rajasthan Power Grid project'
                    },
                    {
                        'name': 'Riya Patel',
                        'email': 'riya.patel@kec.com',
                        'phone': '+91-8765432091',
                        'role': 'Head of Procurement'
                    }
                ]
            },
            'ncc limited': {
                'contacts': [
                    {
                        'name': 'Rajat Reddy',
                        'email': 'rajat.reddy@ncc.co.in',
                        'phone': '+91-9876543319',
                        'role': 'Chief Procurement Officer',
                        'notes': 'Collaborated with JSW Steel\'s team led by Ritu Sharma for steel in the Hyderabad Metro Phase 2'
                    },
                    {
                        'name': 'Ananya Khanna',
                        'email': 'ananya.khanna@ncc.co.in',
                        'phone': '+91-7766554110',
                        'role': 'VP of Procurement'
                    }
                ]
            },
            'adani group': {
                'contacts': [
                    {
                        'name': 'Amit Desai',
                        'email': 'amit.desai@adani.com',
                        'phone': '+91-9876543318',
                        'role': 'Head of Procurement',
                        'notes': 'Worked with JSW Steel\'s team led by Rajesh Nair for steel in the Dhamra Port expansion'
                    },
                    {
                        'name': 'Priya Menon',
                        'email': 'priya.menon@adani.com',
                        'phone': '+91-8765432092',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'tata projects': {
                'contacts': [
                    {
                        'name': 'Rohan Iyer',
                        'email': 'rohan.iyer@tataprojects.com',
                        'phone': '+91-9876543317',
                        'role': 'VP of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Arvind Reddy for steel in the Mumbai Coastal Road project'
                    },
                    {
                        'name': 'Kavita Rao',
                        'email': 'kavita.rao@tataprojects.com',
                        'phone': '+91-7766554109',
                        'role': 'Chief Procurement Officer'
                    }
                ]
            },
            'cidco': {
                'contacts': [
                    {
                        'name': 'Vikram Singh',
                        'email': 'vikram.singh@cidco.in',
                        'phone': '+91-9876543316',
                        'role': 'Director of Procurement',
                        'notes': 'Collaborated with JSW Steel\'s team led by Nandini Patel for steel in the Navi Mumbai Airport project'
                    },
                    {
                        'name': 'Anaya Desai',
                        'email': 'anaya.desai@cidco.in',
                        'phone': '+91-8765432093',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'rvnl': {
                'contacts': [
                    {
                        'name': 'Rajiv Kapoor',
                        'email': 'rajiv.kapoor@rvnl.org',
                        'phone': '+91-9876543315',
                        'role': 'Chief Supply Chain Officer',
                        'notes': 'Worked with JSW Steel\'s team led by Aditya Rao for rail steel in the Delhi-Meerut RRTS project'
                    },
                    {
                        'name': 'Shruti Menon',
                        'email': 'shruti.menon@rvnl.org',
                        'phone': '+91-7766554108',
                        'role': 'Head of Procurement'
                    }
                ]
            },
            'patel engineering': {
                'contacts': [
                    {
                        'name': 'Rakesh Sharma',
                        'email': 'rakesh.sharma@patelengineering.com',
                        'phone': '+91-9876543314',
                        'role': 'VP of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Vikram Choudhary for tunnel steel in the Chenab Railway Bridge'
                    },
                    {
                        'name': 'Anita Reddy',
                        'email': 'anita.reddy@patelengineering.com',
                        'phone': '+91-8765432094',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'larsen & toubro': {
                'contacts': [
                    {
                        'name': 'Rajiv Mehta',
                        'email': 'rajiv.mehta@larsentoubro.com',
                        'phone': '+91-9876543301',
                        'role': 'Chief Procurement Officer',
                        'notes': 'Collaborated with JSW Steel\'s team led by Vikram Singh for high-grade steel in the Mumbai-Ahmedabad Bullet Train project'
                    },
                    {
                        'name': 'Ananya Sharma',
                        'email': 'ananya.sharma@larsentoubro.com',
                        'phone': '+91-7766554101',
                        'role': 'VP of Procurement'
                    }
                ]
            },
            'dilip buildcon': {
                'contacts': [
                    {
                        'name': 'Rohan Verma',
                        'email': 'rohan.verma@dilipbuildcon.com',
                        'phone': '+91-9876543302',
                        'role': 'Director of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Sameer Joshi for structural steel in the Indore Metro project'
                    },
                    {
                        'name': 'Priya Kapoor',
                        'email': 'priya.kapoor@dilipbuildcon.com',
                        'phone': '+91-8765432100',
                        'role': 'Head of Procurement'
                    }
                ]
            }
        }
        
        # Common variations of company names
        self.company_variations = {
            'nhai': ['national highways authority of india', 'nhai', 'national highways'],
            'msrfc': ['msrfc', 'maharashtra state road development corporation', 'msrdc'],
            'kec international': ['kec international', 'kec', 'kec international limited'],
            'ncc limited': ['ncc limited', 'ncc', 'nagarjuna construction company'],
            'adani group': ['adani group', 'adani', 'adani enterprises', 'adani infrastructure'],
            'tata projects': ['tata projects', 'tata projects limited', 'tpl'],
            'cidco': ['cidco', 'city and industrial development corporation'],
            'rvnl': ['rvnl', 'rail vikas nigam limited', 'rail vikas nigam'],
            'patel engineering': ['patel engineering', 'patel engineering ltd', 'patel'],
            'larsen & toubro': ['larsen & toubro', 'l&t', 'l & t', 'larsen and toubro', 'l and t'],
            'dilip buildcon': ['dilip buildcon', 'dilip buildcon limited', 'dbl']
        }

    def _normalize_company_name(self, company_name: str) -> str:
        """Normalize company name for matching."""
        if not company_name:
            return ''
        
        # Convert to lowercase and strip whitespace
        company_name = company_name.lower().strip()
        
        # Log original company name
        self.logger.debug(f"Normalizing company name: {company_name}")
        
        # Remove common prefixes
        prefixes = ['m/s', 'm/s.', 'messrs.', 'messrs']
        for prefix in prefixes:
            if company_name.startswith(prefix):
                company_name = company_name[len(prefix):].strip()
        
        # Remove common suffixes
        suffixes = [
            'limited', 'ltd', 'ltd.', 
            'pvt', 'private', 'public',
            'corporation', 'corp', 'corp.',
            'infrastructure', 'infra',
            'construction', 'constructions',
            'engineering', 'engineers',
            'projects', 'project',
            'builders', 'industries',
            'enterprises', 'company'
        ]
        
        # Split into words and filter out suffixes
        words = company_name.split()
        filtered_words = [word for word in words if word.lower() not in suffixes]
        
        # Rejoin filtered words
        normalized = ' '.join(filtered_words)
        
        # Log normalized name
        self.logger.debug(f"Normalized company name: {normalized}")
        
        return normalized

    def _find_matching_company(self, company_name: str) -> Optional[str]:
        """Find matching company in CRM data using variations."""
        normalized_name = self._normalize_company_name(company_name)
        
        # First try exact match
        if normalized_name in self.crm_data:
            return normalized_name
            
        # Try variations
        for crm_company, variations in self.company_variations.items():
            if any(variation in normalized_name for variation in variations):
                # Make sure it's not just a partial match of a different company
                # by checking if the variation is a significant part of the name
                variation_words = set(normalized_name.split())
                for variation in variations:
                    variation_match_words = set(variation.split())
                    # If more than 50% of the variation words match, consider it a match
                    if len(variation_match_words.intersection(variation_words)) / len(variation_match_words) > 0.5:
                        return crm_company
                        
        # Try partial matches only if the match is significant
        best_match = None
        highest_similarity = 0
        
        for crm_company in self.crm_data.keys():
            # Calculate word overlap similarity
            name_words = set(normalized_name.split())
            crm_words = set(crm_company.split())
            
            if name_words and crm_words:  # Ensure neither set is empty
                # Calculate Jaccard similarity
                similarity = len(name_words.intersection(crm_words)) / len(name_words.union(crm_words))
                
                # Only consider it a match if similarity is high enough
                if similarity > 0.5 and similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match = crm_company
        
        return best_match

    def _check_company_in_crm(self, company_name: str) -> dict:
        """Use LLM to intelligently check if company exists in CRM and get matching details."""
        try:
            # Prepare CRM data for LLM
            crm_companies = list(self.crm_data.keys())
            
            # Create prompt for the LLM
            prompt = f"""Given the company name "{company_name}" and our CRM database containing these companies: {crm_companies},
            please analyze if this company exists in our CRM. Consider company name variations, abbreviations, and common aliases.
            
            Return your response in this format:
            {{
                "found": true/false,
                "matched_company": "exact company name from CRM if found, null if not found",
                "confidence": 0-1 score of match confidence,
                "reasoning": "brief explanation of the match or why no match was found"
            }}
            
            Only return valid JSON, no other text."""

            # Get LLM response using Groq
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes company names and returns JSON responses."},
                    {"role": "user", "content": prompt}
                ],
                model="mixtral-8x7b-32768",  # Using Mixtral model for better reasoning
                temperature=0,
                max_tokens=500
            )

            result = chat_completion.choices[0].message.content
            
            # Ensure we get valid JSON
            try:
                parsed_result = json.loads(result)
                self.logger.info(f"LLM analysis for {company_name}: {parsed_result}")
                return parsed_result
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON response from LLM: {result}")
                return {"found": False, "matched_company": None, "confidence": 0, "reasoning": "Invalid LLM response format"}
            
        except Exception as e:
            self.logger.error(f"Error in LLM company check: {str(e)}")
            return {"found": False, "matched_company": None, "confidence": 0, "reasoning": str(e)}

    def get_company_contacts(self, company_name: str) -> List[Dict]:
        """Get contacts for a company using LLM-driven matching."""
        if not company_name:
            self.logger.warning("Empty company name provided")
            return []
            
        # Use LLM to check CRM
        match_result = self._check_company_in_crm(company_name)
        
        if match_result["found"] and match_result["confidence"] >= 0.8:
            matched_company = match_result["matched_company"]
            if matched_company in self.crm_data:
                self.logger.info(f"Found contacts for company: {matched_company} (confidence: {match_result['confidence']})")
                self.logger.info(f"Match reasoning: {match_result['reasoning']}")
                return self.crm_data[matched_company]['contacts']
        
        # If no confident CRM match, try ContactOut
        self.logger.info(f"No confident CRM match found for {company_name}, trying ContactOut")
        self.logger.info(f"Reason: {match_result.get('reasoning', 'Unknown')}")
        return self._search_contactout(company_name)

    def _search_contactout(self, company_name: str) -> List[Dict]:
        """Search for contacts using ContactOut API."""
        try:
            # Initialize ContactOut client (implement API calls here)
            # This is a placeholder - implement actual ContactOut API integration
            self.logger.info(f"Searching ContactOut for {company_name}")
            return []
        except Exception as e:
            self.logger.error(f"ContactOut search failed: {str(e)}")
            return []
    
    def enrich_project_contacts(self, project: Dict) -> Dict:
        """Enrich project with contact information."""
        try:
            if not project:
                return project
                
            company_name = project.get('company', '')
            if not company_name:
                self.logger.warning("No company name in project")
                return project
            
            # Get contacts using LLM-driven approach
            contacts = self.get_company_contacts(company_name)
            
            if contacts:
                project['contacts'] = contacts
                self.logger.info(f"Added {len(contacts)} contacts for {company_name}")
            else:
                # If no contacts found, add default contact
                project['contacts'] = [{
                    'name': 'Procurement Team',
                    'role': 'Procurement Department',
                    'email': f"procurement@{company_name.lower().replace(' ', '')}.com",
                    'phone': 'N/A'
                }]
                self.logger.warning(f"Using default contact for {company_name}")
            
            return project
            
        except Exception as e:
            self.logger.error(f"Error enriching project contacts: {str(e)}")
            return project 