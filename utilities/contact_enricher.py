import requests
import logging
import json
from config.settings import Config
import re
from datetime import datetime
import time
from scrapers.linkedin_scraper import LinkedInScraper

class ContactEnricher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.crm_data = self._load_crm_data()
        self.linkedin = LinkedInScraper()
        
    def _load_crm_data(self):
        """Load CRM data from the predefined dictionary"""
        crm_data = {
            'larsen & toubro': {
                'contacts': [
                    {
                        'name': 'Arjun Sharma',
                        'role': 'VP of Procurement',
                        'email': 'arjun.sharma@lt.com',
                        'phone': '+91-9876543210'
                    },
                    {
                        'name': 'Priya Patel',
                        'role': 'VP of Procurement',
                        'email': 'priya.patel@lt.com',
                        'phone': '+91-9988776655'
                    }
                ],
                'projects': {
                    'current': 'Mumbai–Ahmedabad High-Speed Rail (MAHSR)',
                    'volume': '150,000 MT (Ongoing)',
                    'materials': 'High-Strength TMT Bars, HR Plates, LRPC',
                    'notes': 'JSW holds >50% market share in steel supply for this project. Strong relationship; exploring opportunities for Delhi–Varanasi HSR project'
                }
            },
            'dilip buildcon': {
                'contacts': [
                    {
                        'name': 'Rohan Verma',
                        'role': 'VP of Procurement',
                        'email': 'rohan.verma@dilipbuildcon.com',
                        'phone': '+91-9765432109'
                    },
                    {
                        'name': 'Sneha Kapoor',
                        'role': 'VP of Procurement',
                        'email': 'sneha.kapoor@dilipbuildcon.com',
                        'phone': '+91-9654321098'
                    }
                ],
                'projects': {
                    'current': 'Thoppur Ghat Section (Tamil Nadu)',
                    'volume': '25,000 MT (Ongoing)',
                    'materials': 'TMT Bars, Structural Steel',
                    'notes': 'Focus on timely delivery and customized steel grades'
                }
            },
            'pnc infratech': {
                'contacts': [
                    {
                        'name': 'Vikram Singh',
                        'role': 'VP of Procurement',
                        'email': 'vikram.singh@pncinfratech.com',
                        'phone': '+91-9543210987'
                    },
                    {
                        'name': 'Deepika Reddy',
                        'role': 'VP of Procurement',
                        'email': 'deepika.reddy@pncinfratech.com',
                        'phone': '+91-9432109876'
                    }
                ],
                'projects': {
                    'current': 'Western Bhopal Bypass',
                    'volume': '30,000 MT (Ongoing)',
                    'materials': 'TMT Bars, Cement-Coated Steel',
                    'notes': 'Seeking long-term supply agreement'
                }
            },
            'hg infra': {
                'contacts': [
                    {
                        'name': 'Amit Patel',
                        'role': 'VP of Procurement',
                        'email': 'amit.patel@hginfra.com',
                        'phone': '+91-9321098765'
                    },
                    {
                        'name': 'Neha Sharma',
                        'role': 'VP of Procurement',
                        'email': 'neha.sharma@hginfra.com',
                        'phone': '+91-9210987654'
                    }
                ],
                'projects': {
                    'current': 'Maharashtra EPC Road Projects',
                    'volume': '40,000 MT (Ongoing)',
                    'materials': 'Structural Steel, Rebar',
                    'notes': 'Focus on green steel options to align with sustainability goals'
                }
            },
            'irb infrastructure': {
                'contacts': [
                    {
                        'name': 'Suresh Kumar',
                        'role': 'VP of Procurement',
                        'email': 'suresh.kumar@irb.com',
                        'phone': '+91-9109876543'
                    },
                    {
                        'name': 'Anjali Iyer',
                        'role': 'VP of Procurement',
                        'email': 'anjali.iyer@irb.com',
                        'phone': '+91-9098765432'
                    }
                ],
                'projects': {
                    'current': 'NH-44 Lalitpur-Sagar-Lakhnadon Section',
                    'volume': '20,000 MT (Ongoing)',
                    'materials': 'High-Tensile Steel, TMT Bars',
                    'notes': 'Exploring toll-operate-transfer (TOT) projects partnership'
                }
            },
            'cube highways': {
                'contacts': [
                    {
                        'name': 'Manish Gupta',
                        'role': 'VP of Procurement',
                        'email': 'manish.gupta@cubehighways.com',
                        'phone': '+91-8987654321'
                    },
                    {
                        'name': 'Kavita Verma',
                        'role': 'VP of Procurement',
                        'email': 'kavita.verma@cubehighways.com',
                        'phone': '+91-8877665544'
                    }
                ],
                'projects': {
                    'current': 'NH-2 Allahabad Bypass',
                    'volume': '15,000 MT (Completed)',
                    'materials': 'Reinforcement Steel, Pre-stressed Cables',
                    'notes': 'Successful project; seeking future collaborations for highway expansions'
                }
            },
            'gr infraprojects': {
                'contacts': [
                    {
                        'name': 'Rajesh Khanna',
                        'role': 'VP of Procurement',
                        'email': 'rajesh.khanna@grinfra.com',
                        'phone': '+91-8765432109'
                    },
                    {
                        'name': 'Shweta Singh',
                        'role': 'VP of Procurement',
                        'email': 'shweta.singh@grinfra.com',
                        'phone': '+91-8654321098'
                    }
                ],
                'projects': {
                    'current': 'Pune Ring Road',
                    'volume': '35,000 MT (Ongoing)',
                    'materials': 'Structural Steel, TMT Bars',
                    'notes': 'Critical project; focusing on just-in-time delivery'
                }
            },
            'afcons infrastructure': {
                'contacts': [
                    {
                        'name': 'Sandeep Malhotra',
                        'role': 'VP of Procurement',
                        'email': 'sandeep.malhotra@afcons.com',
                        'phone': '+91-8543210987'
                    },
                    {
                        'name': 'Nidhi Joshi',
                        'role': 'VP of Procurement',
                        'email': 'nidhi.joshi@afcons.com',
                        'phone': '+91-8432109876'
                    }
                ],
                'projects': {
                    'current': 'Mumbai–Ahmedabad HSR Tunneling',
                    'volume': '18,000 MT (Ongoing)',
                    'materials': 'Tunneling Grade Steel, Support Structures',
                    'notes': 'Specialized steel requirements; close technical collaboration'
                }
            },
            'j kumar infraprojects': {
                'contacts': [
                    {
                        'name': 'Vikrant Kumar',
                        'role': 'VP of Procurement',
                        'email': 'vikrant.kumar@jkumar.com',
                        'phone': '+91-8321098765'
                    },
                    {
                        'name': 'Alisha Khan',
                        'role': 'VP of Procurement',
                        'email': 'alisha.khan@jkumar.com',
                        'phone': '+91-8210987654'
                    }
                ],
                'projects': {
                    'current': 'Navi Mumbai Coastal Road',
                    'volume': '12,000 MT (Ongoing)',
                    'materials': 'Corrosion-Resistant Steel, Marine-Grade Rebar',
                    'notes': 'Focus on durability in coastal environments'
                }
            },
            'megha engineering': {
                'contacts': [
                    {
                        'name': 'Gaurav Bhatia',
                        'role': 'VP of Procurement',
                        'email': 'gaurav.bhatia@meil.in',
                        'phone': '+91-8109876543'
                    },
                    {
                        'name': 'Tanvi Reddy',
                        'role': 'VP of Procurement',
                        'email': 'tanvi.reddy@meil.in',
                        'phone': '+91-8098765432'
                    }
                ],
                'projects': {
                    'current': 'Pune Ring Road, Mahi Multi Villages Scheme',
                    'volume': '45,000 MT (Ongoing)',
                    'materials': 'High-Grade Steel, Piping Steel',
                    'notes': 'Key partner; exploring irrigation and infrastructure projects'
                }
            }
        }
        return crm_data
    
    def _search_apollo_contacts(self, company_name):
        """Search for procurement contacts using Apollo API"""
        try:
            headers = {
                'accept': 'application/json',
                'Cache-Control': 'no-cache',
                'Content-Type': 'application/json',
                'x-api-key': self.api_key
            }

            # First search for the company
            company_data = {
                'q_organization_name': company_name,
                'page': 1,
                'per_page': 1
            }

            company_response = requests.post(
                'https://api.apollo.io/api/v1/organizations/search',
                headers=headers,
                json=company_data
            )
            company_response.raise_for_status()
            company_info = company_response.json()

            if not company_info.get('organizations'):
                self.logger.warning(f"No company found in Apollo for {company_name}")
                return []

            organization_id = company_info['organizations'][0]['id']

            # Search for procurement contacts
            contact_data = {
                'organization_ids': [organization_id],
                'titles': [
                    'Procurement',
                    'Purchasing',
                    'Supply Chain',
                    'Materials',
                    'Sourcing',
                    'Buyer',
                    'Vendor'
                ],
                'seniorities': [
                    'director',
                    'vp',
                    'head',
                    'manager',
                    'lead'
                ],
                'page': 1,
                'per_page': 10
            }

            contact_response = requests.post(
                'https://api.apollo.io/api/v1/people/search',
                headers=headers,
                json=contact_data
            )
            contact_response.raise_for_status()
            contact_data = contact_response.json()

            contacts = []
            for person in contact_data.get('people', []):
                contact = {
                    'name': f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                    'role': person.get('title', ''),
                    'email': person.get('email', ''),
                    'phone': person.get('phone_number', ''),
                    'location': f"{person.get('city', '')}, {person.get('state', '')}".strip(', '),
                    'source': 'Apollo'
                }
                contacts.append(contact)

            return contacts

        except Exception as e:
            self.logger.error(f"Apollo API search failed for {company_name}: {str(e)}")
            return []
    
    def enrich_project_contacts(self, project_info):
        """Find procurement contacts for a company using CRM data and project info"""
        try:
            company_name = project_info.get('company', '')
            if not company_name or company_name == 'Unknown Company':
                return {
                    'status': 'error',
                    'message': 'Invalid company name'
                }
            
            # First check CRM data
            crm_info = self._get_crm_info(company_name)
            if crm_info:
                self.logger.info(f"Found existing contacts in CRM for {company_name}")
                return {
                    'status': 'success',
                    'source': 'CRM',
                    'contacts': crm_info['contacts'],
                    'relationship': {
                        'current_project': crm_info['projects']['current'],
                        'volume': crm_info['projects']['volume'],
                        'materials': crm_info['projects']['materials'],
                        'notes': crm_info['projects']['notes']
                    },
                    'priority': self._determine_priority(project_info)
                }
            
            # If no CRM data, use any contacts provided in the project info
            if project_info.get('contacts'):
                self.logger.info(f"Using project contacts for {company_name}")
                return {
                    'status': 'success',
                    'source': 'Project Data',
                    'contacts': project_info['contacts'],
                    'relationship': {
                        'current_project': 'No existing relationship',
                        'volume': 'N/A',
                        'materials': 'N/A',
                        'notes': 'New potential customer'
                    },
                    'priority': self._determine_priority(project_info)
                }
            
            # Search LinkedIn as a fallback
            linkedin_contacts = self._search_linkedin(company_name)
            if linkedin_contacts:
                self.logger.info(f"Found LinkedIn contacts for {company_name}")
                return {
                    'status': 'success',
                    'source': 'LinkedIn',
                    'contacts': linkedin_contacts,
                    'relationship': {
                        'current_project': 'No existing relationship',
                        'volume': 'N/A',
                        'materials': 'N/A',
                        'notes': 'New potential customer'
                    },
                    'priority': self._determine_priority(project_info)
                }
            
            self.logger.warning(f"No contacts found for {company_name}")
            return {
                'status': 'not_found',
                'message': f"No contacts found for {company_name}"
            }
            
        except Exception as e:
            self.logger.error(f"Error enriching contacts for {company_name}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _determine_priority(self, project_info):
        """Determine project priority based on various factors"""
        priority = "NORMAL"
        priority_indicators = []
        
        # Check for explicit priority marking
        title = project_info.get('title', '').lower()
        description = project_info.get('description', '').lower()
        full_text = f"{title} {description}"
        
        if '[high priority]' in full_text:
            priority = "HIGH"
            priority_indicators.append("Marked as High Priority")
        
        # Check steel requirement
        steel_req = project_info.get('steel_requirement', 0)
        if steel_req > 1000:
            priority = "HIGH"
            priority_indicators.append(f"Large steel requirement: {steel_req} MT")
        
        # Check timeline
        start_date = project_info.get('start_date')
        if start_date and isinstance(start_date, datetime):
            months_to_start = (start_date - datetime.now()).days / 30
            if months_to_start <= 3:
                priority = "HIGH"
                priority_indicators.append("Starting within 3 months")
        
        # Check for key terms
        key_terms = ['metro', 'railway', 'infrastructure', 'government']
        if any(term in full_text for term in key_terms):
            priority = "HIGH"
            priority_indicators.append("Strategic project type")
        
        return {
            'level': priority,
            'indicators': priority_indicators
        }
    
    def _normalize_company_name(self, name):
        """Normalize company name for matching"""
        # Remove common suffixes and clean the name
        name = name.lower()
        suffixes = ['limited', 'ltd', 'pvt', 'private', 'corporation', 'corp', 'inc', 'infrastructure', 'infra']
        for suffix in suffixes:
            name = name.replace(suffix, '').strip()
        return name.strip()
    
    def _get_crm_info(self, company_name):
        """Get company information from CRM data"""
        # Try exact match first
        if company_name in self.crm_data:
            return self.crm_data[company_name]
        
        # Try partial matches
        for crm_company, data in self.crm_data.items():
            if company_name in crm_company or crm_company in company_name:
                return data
        
        return None
    
    def _search_linkedin(self, company_name):
        """Search for procurement contacts on LinkedIn"""
        try:
            procurement_roles = [
                        'procurement',
                        'purchasing',
                        'supply chain',
                        'materials',
                        'sourcing',
                        'buyer',
                'vendor management'
            ]
            
            # Search for employees with procurement roles
            profiles = self.linkedin.search_company_employees(company_name, procurement_roles)
            
            # Get detailed information for each profile
            detailed_contacts = []
            for profile in profiles:
                if self._is_relevant_role(profile['title']):
                    details = self.linkedin.get_profile_details(profile['profile_url'])
                    if details:
                        detailed_contacts.append({
                            'name': details['name'],
                            'role': details['title'],
                            'location': details.get('location', ''),
                            'profile_url': profile['profile_url'],
                            'experience': details.get('experience', []),
                            'source': 'LinkedIn'
                        })
            
            return detailed_contacts
            
        except Exception as e:
            self.logger.error(f"LinkedIn search failed for {company_name}: {str(e)}")
            return []
    
    def _is_relevant_role(self, title):
        """Check if the role is relevant for procurement"""
        title_lower = title.lower()
        relevant_terms = [
            'procurement', 'purchase', 'purchasing', 'buyer', 'buying',
            'supply chain', 'vendor', 'material', 'sourcing', 'category',
            'contract', 'tender', 'bid'
        ]
        
        relevant_positions = [
            'director', 'head', 'vp', 'manager', 'lead', 'chief'
        ]
        
        return (
            any(term in title_lower for term in relevant_terms) and
            any(pos in title_lower for pos in relevant_positions)
        )
    
    def _merge_contacts(self, linkedin_contacts, apollo_contacts):
        """Merge contacts from LinkedIn and Apollo, removing duplicates"""
        merged = []
        seen_names = set()
        
        # Add LinkedIn contacts first
        for contact in linkedin_contacts:
            name = contact['name'].lower()
            if name not in seen_names:
                seen_names.add(name)
                merged.append(contact)
        
        # Add Apollo contacts if they're not duplicates
        for contact in apollo_contacts:
            name = contact['name'].lower()
            if name not in seen_names:
                seen_names.add(name)
                merged.append(contact)
        
        return merged
    
    def _calculate_similarity(self, str1, str2):
        """Calculate string similarity using Levenshtein distance"""
        if not str1 or not str2:
            return 0
        
        # Convert to sets of words for better matching
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())
        
        # Calculate Jaccard similarity
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0 