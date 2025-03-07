"""Email handler for sending project notifications."""

import logging
from datetime import datetime, timedelta
import re
from config.settings import Config

logger = logging.getLogger(__name__)

class EmailHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.team_emails = Config.TEAM_EMAILS

    def determine_product_team(self, project):
        """Determine the most relevant product team based on project details"""
        try:
            # Handle string input
            if isinstance(project, str):
                text = project.lower()
            # Handle dictionary input
            elif isinstance(project, dict):
                title = project.get('title', '').lower()
                description = project.get('description', '').lower()
                text = f"{title} {description}"
            else:
                self.logger.error(f"Invalid project type: {type(project)}")
                return 'TMT_BARS'  # Default team
            
            # Check for specific keywords in order of priority
            if any(word in text for word in ['metro', 'railway', 'rail', 'train']):
                return 'HR_CR_PLATES'
            elif any(word in text for word in ['solar', 'renewable', 'pv']):
                return 'SOLAR'
            elif any(word in text for word in ['building', 'residential', 'commercial']):
                return 'TMT_BARS'
            elif any(word in text for word in ['industrial', 'factory', 'plant']):
                return 'HR_CR_PLATES'
            elif any(word in text for word in ['road', 'highway', 'bridge']):
                return 'TMT_BARS'
            
            return 'TMT_BARS'
            
        except Exception as e:
            self.logger.error(f"Error in determine_product_team: {str(e)}")
            return 'TMT_BARS'  # Default team in case of error

    def calculate_steel_requirement(self, project, product_type):
        """Calculate steel requirement based on project type and value"""
        try:
            # Handle string input
            if isinstance(project, str):
                text = project.lower()
                value_in_cr = 0
            # Handle dictionary input
            elif isinstance(project, dict):
                value_in_cr = project.get('value', 0)
                title = project.get('title', '').lower()
                description = project.get('description', '').lower()
                text = f"{title} {description}"
            else:
                self.logger.error(f"Invalid project type: {type(project)}")
                return 0
            
            # Get the rates for the product type
            rates = Config.STEEL_RATES.get(product_type, {})
            rate = rates.get('default', 10)  # Default rate if nothing else matches
            
            # Find the most specific rate
            for category, category_rate in rates.items():
                if category != 'default' and category in text:
                    rate = category_rate
                    break
            
            steel_tons = value_in_cr * rate * 0.8  # Using 0.8 as conservative factor
            return steel_tons
            
        except Exception as e:
            self.logger.error(f"Error in calculate_steel_requirement: {str(e)}")
            return 0  # Return 0 in case of error

    def _format_project_for_email(self, project):
        """Format a single project for HTML email."""
        try:
            # Get company name and CRM data
            company_name = project.get('company', '')
            crm_data = self._get_crm_info(company_name)
            has_relationship = bool(crm_data)
            is_jsw_project = 'jsw' in company_name.lower()

            # Get contacts from CRM data only
            contacts = []
            if crm_data and 'contacts' in crm_data:
                contacts = crm_data.get('contacts', [])
            
            # Format contacts HTML
            contacts_html = self._format_contacts_html(contacts)
            
            # Create HTML for single project
            html = f'''
                <div class="project-card">
                    {self._format_project_header(project, is_jsw_project)}
                    {self._format_project_details(project)}
                    {self._format_relationship_section(company_name, has_relationship, crm_data)}
                    {contacts_html}
                </div>
            '''
            
            return html
            
        except Exception as e:
            self.logger.error(f"Error formatting project for email: {str(e)}")
            return ""

    def _format_contacts_html(self, contacts):
        """Format contacts section for email."""
        if not contacts:
            return '''
                <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                    <p style="margin: 0; color: #5f6368;">No contact information available in CRM.</p>
                </div>
            '''
        
        contacts_html = '<div style="margin-top: 15px;">'
        contacts_html += '<h4 style="color: #1a1a1a; margin-bottom: 10px;">Key Contacts:</h4>'
        
        for contact in contacts:
            contacts_html += f'''
                <div style="margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                    <div style="font-weight: bold; color: #1a1a1a;">{contact.get('name', '')}</div>
                    <div style="color: #6c757d; font-size: 14px;">{contact.get('title', '')}</div>
                    <div style="color: #6c757d; font-size: 14px;">{contact.get('email', '')}</div>
                    <div style="color: #6c757d; font-size: 14px;">{contact.get('phone', '')}</div>
                </div>
            '''
        
        contacts_html += '</div>'
        return contacts_html

    def _format_project_header(self, project, is_jsw_project):
        """Format the project header for email."""
        priority_tag = next((tag for tag in project.get('tags', []) if 'Priority' in tag), 'Normal Priority')
        is_high_priority = 'High' in priority_tag
        priority_color = '#dc3545' if is_high_priority else '#2e7d32'
        priority_bg = '#fde8e8' if is_high_priority else '#e8f5e9'
        priority_tag = 'High Priority' if is_high_priority else 'Normal Priority'
        
        html = f'''
            <div style="margin-bottom: 15px;">
                <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 14px; background: {priority_bg}; color: {priority_color};">
                    {priority_tag}
                </span>
                {
                '<span style="display: inline-block; margin-left: 10px; padding: 2px 8px; border-radius: 4px; font-size: 14px; background: #fff3cd; color: #856404;">JSW Project</span>'
                if is_jsw_project else ''
                }
            </div>
            
            <h4 style="color: #424242; font-size: 20px; margin: 0 0 20px 0;">{project.get('title', '')}</h4>
        '''
        return html

    def _format_project_details(self, project):
        """Format the project details for email."""
        html = f'''
            <div style="margin-bottom: 20px;">
                <div style="font-size: 16px; margin-bottom: 12px;">
                    <strong style="color: #1a1a1a;">Primary:</strong> TMT Bars: ~{project.get('steel_requirements', {}).get('primary', {}).get('quantity', 0):,}MT
                </div>
                <div style="font-size: 16px; margin-bottom: 12px;">
                    <strong style="color: #1a1a1a;">Secondary:</strong> HR Plates: ~{project.get('steel_requirements', {}).get('secondary', {}).get('quantity', 0):,}MT
                </div>
                <div style="font-size: 16px; margin-bottom: 12px;">
                    <strong style="color: #1a1a1a;">Work Begins:</strong> {project.get('start_date', datetime.now()).strftime('%B %Y')} - {project.get('end_date', datetime.now() + timedelta(days=365)).strftime('%B %Y')}
                </div>
            </div>
        '''
        return html

    def _format_relationship_section(self, company_name, has_relationship, crm_data):
        """Format the relationship section for email."""
        if is_jsw_project:
            relationship_html = f'''
                <div style="background: #fff3cd; padding: 15px; border-radius: 6px; margin: 15px 0; border: 1px solid #ffeeba;">
                    <div style="color: #856404; font-weight: bold; margin-bottom: 10px;">⚠️ JSW Project Alert</div>
                    <div style="color: #856404;">
                        This project involves JSW. {
                        "No existing relationship data found in CRM." if not has_relationship else "Current relationship data found in CRM."
                        }
                    </div>
                    <div style="margin-top: 15px;">
                        <button onclick="this.innerHTML='Done'; this.style.background='#28a745'; this.style.color='white'; this.disabled=true;" 
                           style="display: inline-block; background: #ffc107; color: #000; padding: 8px 15px; 
                                  text-decoration: none; border-radius: 4px; font-weight: bold; border: none; cursor: pointer;">
                            Update Relationship Status
                        </button>
                    </div>
                </div>
            '''
        elif has_relationship:
            relationship_html = f'''
                <div class="mb-2">
                    <strong style="color: #1a1a1a;">Current Project:</strong> {crm_data.get('projects', {}).get('current', 'No current project')}
                </div>
                <div class="mb-2">
                    <strong style="color: #1a1a1a;">Volume:</strong> {crm_data.get('projects', {}).get('volume', 'N/A')}
                </div>
                <div class="mb-2">
                    <strong style="color: #1a1a1a;">Materials:</strong> {crm_data.get('projects', {}).get('materials', 'N/A')}
                </div>
                <div>
                    <strong style="color: #1a1a1a;">Notes:</strong> {crm_data.get('projects', {}).get('notes', 'No additional notes')}
                </div>
            '''
        else:
            relationship_html = '''
                <div>
                    <strong style="color: #1a1a1a;">No existing relationship found</strong>
                    <div style="margin-top: 10px;">
                        <button onclick="this.innerHTML='Done'; this.style.background='#28a745'; this.style.color='white'; this.disabled=true;" 
                           style="display: inline-block; background: #e9ecef; color: #495057; padding: 8px 15px; 
                                  text-decoration: none; border-radius: 4px; font-size: 14px; border: none; cursor: pointer;">
                            Add Relationship Data
                        </button>
                    </div>
                </div>
            '''
        return relationship_html

    def _get_team_emails(self, teams): 
        """Get email addresses for teams"""
        try:
            email_set = set()  # Use a set to automatically deduplicate emails
            
            if isinstance(teams, list) and all(isinstance(t, str) for t in teams):
                for team in teams:
                    if team in self.team_emails:
                        # Split email string in case it contains multiple emails
                        team_emails = [email.strip() for email in self.team_emails[team].split(',')]
                        email_set.update(team_emails)
            
            elif isinstance(teams, str):
                if teams in self.team_emails:
                    team_emails = [email.strip() for email in self.team_emails[teams].split(',')]
                    email_set.update(team_emails)
            
            elif isinstance(teams, dict):
                if teams.get('primary') in self.team_emails:
                    team_emails = [email.strip() for email in self.team_emails[teams['primary']].split(',')]
                    email_set.update(team_emails)
                if teams.get('secondary') in self.team_emails:
                    team_emails = [email.strip() for email in self.team_emails[teams['secondary']].split(',')]
                    email_set.update(team_emails)
            
            # Convert set back to list, removing any empty strings
            return [email for email in email_set if email]
            
        except Exception as e:
            self.logger.error(f"Error getting team emails: {str(e)}")
            return [] 