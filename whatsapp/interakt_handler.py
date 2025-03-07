"""Interakt WhatsApp handler for sending project notifications."""

import logging
from datetime import datetime, timedelta
import requests
from config.settings import Config
import time
import base64
import re
from urllib.parse import urlparse

class InteraktHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = Config.INTERAKT_API_KEY
        # List of phone numbers to send notifications to
        self.phone_numbers = ["918484926925", "917715018407"]
        self.base_url = "https://api.interakt.ai/v1/public/message/"
        self.enabled = bool(self.api_key and self.phone_numbers)
        
        # Initialize session with retries
        self.session = requests.Session()
        
        # Initialize Perplexity client
        from scrapers.perplexity_client import PerplexityClient
        self.perplexity = PerplexityClient()
        
        # Store project context
        self.project_context = {}
        
        if self.enabled:
            self.logger.info(f"Interakt WhatsApp notifications enabled. Target numbers: {', '.join(self.phone_numbers)}")
            # Validate API key format
            if not self._is_valid_api_key(self.api_key):
                self.logger.error("Invalid API key format")
                self.enabled = False
        else:
            self.logger.error("Interakt configuration incomplete")
    
    def _is_valid_api_key(self, api_key):
        """Validate if the API key is properly base64 encoded"""
        try:
            # Try to decode the API key
            decoded = base64.b64decode(api_key).decode('utf-8')
            return ':' in decoded  # Basic auth typically contains a colon
        except Exception:
            return False
            
    def _format_phone_number(self, phone):
        """Format phone number to match Interakt requirements"""
        # Remove all non-digit characters
        clean_number = ''.join(filter(str.isdigit, phone))
        
        # Validate length (assuming Indian numbers)
        if len(clean_number) < 10 or len(clean_number) > 12:
            self.logger.error(f"Invalid phone number length: {len(clean_number)} digits")
            return None
            
        # Remove country code if present
        if clean_number.startswith('91'):
            clean_number = clean_number[2:]
            
        return clean_number
    
    def handle_incoming_message(self, phone_number, message_text):
        """Handle incoming WhatsApp messages using Perplexity AI"""
        try:
            self.logger.info(f"Received message from {phone_number}: {message_text}")
            
            # Get project context for this user
            context = self.project_context.get(phone_number, {})
            
            # Prepare context for AI
            ai_context = ""
            if context:
                ai_context = f"""
                Project Context:
                Title: {context.get('title')}
                Company: {context.get('company')}
                Value: ₹{context.get('value', 0)} Crore
                Description: {context.get('description')}
                Steel Requirements: {context.get('steel_requirements', {})}
                Start Date: {context.get('start_date')}
                End Date: {context.get('end_date')}
                Source: {context.get('source_url')}
                """
            
            # Add system context
            ai_context += """
            You are a helpful AI assistant for JSW Steel's project discovery system. 
            You help users understand project details, steel requirements, and procurement opportunities.
            Keep responses concise and focused on steel/construction aspects.
            If you don't have enough context, ask for clarification.
            """
            
            # Get AI response
            response = self.perplexity.get_project_info(ai_context + "\n\nUser question: " + message_text)
            
            # Send response back via WhatsApp
            self._send_whatsapp_response(phone_number, response)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling incoming message: {str(e)}")
            error_msg = "Sorry, I encountered an error processing your message. Please try again."
            self._send_whatsapp_response(phone_number, error_msg)
            return False
            
    def _send_whatsapp_response(self, phone_number, message):
        """Send WhatsApp response to a specific number"""
        try:
            headers = {
                'Authorization': f'Basic {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "userId": f"chat_{phone_number}",
                "fullPhoneNumber": phone_number,
                "campaignId": "festive_giveaway",
                "type": "Text",
                "data": {
                    "message": message
                }
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.json().get('result') is True:
                self.logger.info(f"Response sent successfully to {phone_number}")
                return True
            else:
                self.logger.error(f"Failed to send response to {phone_number}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp response: {str(e)}")
            return False
    
    def _format_overview_message(self, projects):
        """Format overview message for multiple projects"""
        overview = f"🏗️ *New Project Opportunities*\n\nFound {len(projects)} new projects:\n"
        for idx, project in enumerate(projects, 1):
            overview += f"\n{idx}. {project['company']} - {project['title']}"
            if project.get('value'):
                overview += f" (₹{project['value']:.1f} Cr)"
        return overview
    
    def _extract_company_domain(self, url):
        """Extract company domain from URL"""
        try:
            parsed = urlparse(url)
            # Get the domain without www.
            domain = parsed.netloc.replace('www.', '')
            return domain
        except Exception as e:
            self.logger.error(f"Error extracting domain: {str(e)}")
            return None

    def _format_project_message(self, project, idx):
        """Format a single project message"""
        try:
            message = f"*{project.get('title', 'N/A')}*\n\n"
            
            message += f"*Company:* {project.get('company', 'N/A')}\n\n"
            
            if project.get('value'):
                message += f"*Value:* ₹{float(project['value']):.1f} Crore\n"
            
            if project.get('start_date'):
                message += f"*Start Date:* {project['start_date'].strftime('%B %Y')}\n"
            if project.get('end_date'):
                message += f"*End Date:* {project['end_date'].strftime('%B %Y')}\n"
            message += "\n"
            
            if project.get('steel_requirements'):
                message += "*Steel Requirements:*\n"
                steel_reqs = project['steel_requirements']
                if isinstance(steel_reqs, dict):
                    for key, value in steel_reqs.items():
                        if isinstance(value, dict):
                            message += f"• {value.get('type', key)}: {value.get('quantity', 0):,} MT\n"
                        elif isinstance(value, (int, float)):
                            message += f"• {key}: {value:,} MT\n"
                message += "\n"
            
            if project.get('source_url'):
                source_url = project['source_url']
                message += f"*Source:* {source_url}\n"
                
                # Extract and add company domain if available
                company_domain = self._extract_company_domain(source_url)
                if company_domain:
                    message += f"*Company Website:* https://{company_domain}\n"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting project message: {str(e)}")
            return f"Error formatting project #{idx}. Please check the logs."

    def test_project_message(self):
        """Test sending a real project message"""
        test_project = {
            'title': 'Test Project - Metro Construction',
            'company': 'ABC Constructions',
            'value': 850.5,
            'description': 'Major metro construction project in Mumbai',
            'start_date': datetime.now(),
            'end_date': datetime.now() + timedelta(days=365),
            'steel_requirements': {
                'primary': {'type': 'TMT Bars', 'quantity': 12000},
                'secondary': {'type': 'HR Plates', 'quantity': 6000},
                'total': 18000
            },
            'contacts': [{
                'name': 'Rajesh Kumar',
                'role': 'Procurement Manager',
                'email': 'rajesh.k@abcconstructions.com',
                'phone': '+91 98765 43210'
            }],
            'source_url': 'https://example.com/project'
        }
        
        message = self._format_project_message(test_project, 1)
        overall_success = True
        
        for phone in self.phone_numbers:
            # Format phone number correctly
            phone_number = self._format_phone_number(phone)
            if not phone_number:
                self.logger.error(f"Invalid phone number format for {phone}")
                overall_success = False
                continue
                
            payload = {
                "countryCode": "91",
                "phoneNumber": phone_number,
                "type": "Text",
                "data": {
                    "message": message
                }
            }
            
            headers = {
                'Authorization': f'Basic {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            try:
                self.logger.info(f"Sending test project message to {phone_number}...")
                self.logger.debug(f"Using payload with phone: {phone_number}")
                
                # Simple request with retries
                for attempt in range(3):
                    try:
                        response = requests.post(
                            self.base_url,
                            headers=headers,
                            json=payload,
                            timeout=30
                        )
                        
                        self.logger.info(f"Response Status for {phone_number}: {response.status_code}")
                        self.logger.info(f"Response Body for {phone_number}: {response.text}")
                        
                        response_data = response.json()
                        if response_data.get('result') is True:
                            self.logger.info(f"Project message sent successfully to {phone_number}")
                            break
                        else:
                            self.logger.error(f"Failed to send project message to {phone_number}: {response.text}")
                            overall_success = False
                            break
                            
                    except requests.exceptions.RequestException as e:
                        if attempt == 2:  # Last attempt
                            self.logger.error(f"Failed all retries for {phone_number}")
                            overall_success = False
                            raise
                        time.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue
                        
            except Exception as e:
                self.logger.error(f"Error sending test project message to {phone_number}: {str(e)}")
                overall_success = False
                
        return overall_success

    def send_project_opportunities(self, projects):
        """Send a batch of project opportunities via WhatsApp.
        
        Args:
            projects (list): List of project dictionaries containing project details
            
        Returns:
            bool: True if all messages were sent successfully, False otherwise
        """
        self.logger.info(f"Sending {len(projects)} project opportunities via WhatsApp")
        
        # JSW filtering terms
        jsw_terms = [
            'jsw', 'jindal', 'js steel', 'jsw steel', 'jindal steel',
            'jsw neosteel', 'jsw trusteel', 'neosteel', 'trusteel',
            'jsw fastbuild', 'jsw galvalume', 'jsw coated',
            'jsw to supply', 'jsw supplies', 'jsw to provide',
            'jsw provides', 'jsw to deliver', 'jsw delivers'
        ]
        
        # Filter out JSW projects first
        filtered_projects = []
        for project in projects:
            try:
                # Skip JSW-related projects
                title = str(project.get('title', '')).lower()
                desc = str(project.get('description', '')).lower()
                company = str(project.get('company', '')).lower()
                all_text = f"{title} {desc} {company}"
                
                if any(term in all_text for term in jsw_terms):
                    self.logger.info(f"Skipping JSW-related project: {project.get('title')}")
                    continue
                    
                filtered_projects.append(project)
            except Exception as e:
                self.logger.error(f"Error filtering project {project.get('title')}: {str(e)}")
                continue
        
        if not filtered_projects:
            self.logger.warning("No non-JSW projects to send")
            return True
            
        self.logger.info(f"Sending {len(filtered_projects)} non-JSW projects")
        overall_success = True
        
        # Create overview message with filtered projects
        overview_message = self._format_overview_message(filtered_projects)
        for phone in self.phone_numbers:
            phone_number = self._format_phone_number(phone)
            if not phone_number:
                self.logger.error(f"Invalid phone number format for {phone}")
                overall_success = False
                continue
                
            # Send overview message
            payload = {
                "countryCode": "91",
                "phoneNumber": phone_number,
                "type": "Text",
                "data": {
                    "message": overview_message
                }
            }
            
            headers = {
                'Authorization': f'Basic {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                if not response.json().get('result'):
                    self.logger.error(f"Failed to send overview to {phone_number}")
                    overall_success = False
            except Exception as e:
                self.logger.error(f"Error sending overview to {phone_number}: {str(e)}")
                overall_success = False
        
        # Then send individual project messages for filtered projects
        for idx, project in enumerate(filtered_projects, 1):
            try:
                # Format project message
                message = self._format_project_message(project, idx)
                
                # Send to all phone numbers
                for phone in self.phone_numbers:
                    phone_number = self._format_phone_number(phone)
                    if not phone_number:
                        self.logger.error(f"Invalid phone number format for {phone}")
                        overall_success = False
                        continue
                        
                    payload = {
                        "countryCode": "91",
                        "phoneNumber": phone_number,
                        "type": "Text",
                        "data": {
                            "message": message
                        }
                    }
                    
                    headers = {
                        'Authorization': f'Basic {self.api_key}',
                        'Content-Type': 'application/json'
                    }
                    
                    try:
                        response = requests.post(
                            self.base_url,
                            headers=headers,
                            json=payload,
                            timeout=30
                        )
                        if not response.json().get('result'):
                            self.logger.error(f"Failed to send project {project.get('title')} to {phone_number}")
                            overall_success = False
                    except Exception as e:
                        self.logger.error(f"Error sending project {project.get('title')} to {phone_number}: {str(e)}")
                        overall_success = False
                        
            except Exception as e:
                self.logger.error(f"Error processing project {project.get('title')}: {str(e)}")
                overall_success = False
                
        return overall_success
