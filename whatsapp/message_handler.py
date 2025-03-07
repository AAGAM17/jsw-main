import json
import logging
from datetime import datetime
from .twilio_client import TwilioClient
from scrapers.perplexity_client import PerplexityClient
from scrapers.metro_scraper import MetroScraper

class WhatsAppHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.twilio = TwilioClient()
        self.perplexity = PerplexityClient()
        self.metro_scraper = MetroScraper()
        self.sent_opportunities = self._load_sent_opportunities()
        self.excluded_opportunities = self._load_excluded_opportunities()
        
        # Define menu options
        self.MAIN_MENU = """
🔍 *Available Commands*:

1️⃣ Type *SHOW* to view latest opportunities
2️⃣ Type *FILTER* to set value filters
3️⃣ Type *SAVED* to view saved opportunities
4️⃣ Type *HELP* for assistance
5️⃣ Type *STOP* to unsubscribe

Reply with the command you'd like to use.
"""
        
        self.HELP_MESSAGE = """
*JSW Steel Project Bot Help*

*Available Commands:*
- *SHOW* - View latest project opportunities
- *FILTER* - Set project value filters
- *SAVED* - View your saved opportunities
- *HELP* - Show this help message
- *STOP* - Unsubscribe from updates

*When viewing opportunities:*
- Reply with project number to get details
- Type *SAVE #* to save an opportunity
- Type *EXCLUDE #* to hide an opportunity
- Type *MORE* to see more opportunities

*Need assistance?*
Type *CONTACT* to speak with a representative.
"""
        
    def _load_sent_opportunities(self):
        try:
            with open('data/sent_opportunities.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
            
    def _load_excluded_opportunities(self):
        try:
            with open('data/excluded_opportunities.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
            
    def _save_sent_opportunities(self):
        with open('data/sent_opportunities.json', 'w') as f:
            json.dump(self.sent_opportunities, f)
            
    def _save_excluded_opportunities(self):
        with open('data/excluded_opportunities.json', 'w') as f:
            json.dump(self.excluded_opportunities, f)
            
    def handle_message(self, message_body, from_number):
        """Handle incoming WhatsApp messages"""
        try:
            message_lower = message_body.lower().strip()
            
            # Main menu commands
            if message_lower in ['menu', 'start', 'hi', 'hello']:
                self._send_main_menu(from_number)
                
            elif message_lower == 'help':
                self.twilio.send_whatsapp(self.HELP_MESSAGE, from_number)
                
            elif message_lower == 'show':
                self._send_opportunities(from_number)
                
            elif message_lower == 'filter':
                self._send_filter_options(from_number)
                
            elif message_lower == 'saved':
                self._show_saved_opportunities(from_number)
                
            elif message_lower == 'stop':
                self._handle_unsubscribe(from_number)
                
            # Project interaction commands
            elif message_lower.startswith('save #'):
                project_num = message_lower.replace('save #', '').strip()
                self._save_opportunity(project_num, from_number)
                
            elif message_lower.startswith('exclude #'):
                project_num = message_lower.replace('exclude #', '').strip()
                self._exclude_opportunity(project_num, from_number)
                
            elif message_lower == 'more':
                self._send_more_opportunities(from_number)
                
            elif message_lower.isdigit():
                self._send_project_details(message_lower, from_number)
                
            else:
                self.twilio.send_whatsapp("I didn't understand that command. Type *HELP* to see available options.", from_number)
                
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
            self.twilio.send_whatsapp("Sorry, something went wrong. Please try again later.", from_number)
    
    def _send_main_menu(self, recipient):
        """Send the main menu options"""
        welcome_msg = "👋 Welcome to JSW Steel Project Bot!\n\n" + self.MAIN_MENU
        self.twilio.send_whatsapp(welcome_msg, recipient)
    
    def _send_opportunities(self, recipient):
        """Send latest opportunities"""
        # Get projects from both sources
        metro_projects = self.metro_scraper.scrape_latest_news()
        ai_projects = self.perplexity.research_infrastructure_projects()
        
        # Combine and filter projects
        all_projects = []
        for project in metro_projects + ai_projects:
            project_id = f"{project['company']}_{project['title']}".lower().replace(" ", "_")
            
            # Skip if already sent or excluded
            if (project_id in self.sent_opportunities or 
                project_id in self.excluded_opportunities):
                continue
                
            # Convert value to lakhs for threshold check (20 lakhs)
            value_in_lakhs = project.get('value', 0) * 100  # Convert crores to lakhs
            if value_in_lakhs >= 20:
                project['id'] = project_id
                all_projects.append(project)
        
        if not all_projects:
            self.twilio.send_whatsapp("No new opportunities found at the moment. Please check back later.", recipient)
            return
            
        # Sort by priority (value and recency)
        sorted_projects = sorted(
            all_projects,
            key=lambda x: (x.get('value', 0), x.get('start_date', datetime.now())),
            reverse=True
        )[:5]  # Cap at 5 opportunities
        
        # Send overview message
        overview = f"📊 Found {len(sorted_projects)} new opportunities:\n\n"
        for idx, project in enumerate(sorted_projects, 1):
            overview += f"{idx}. {project['company']} - {project['title']}\n"
        
        overview += "\n*Reply with a number (1-5) to see project details*"
        self.twilio.send_whatsapp(overview, recipient)
        
        # Store projects in session for later reference
        self.current_projects = sorted_projects
        
    def _send_project_details(self, project_num, recipient):
        """Send detailed project information"""
        try:
            idx = int(project_num) - 1
            if not hasattr(self, 'current_projects') or idx >= len(self.current_projects):
                self.twilio.send_whatsapp("Invalid project number. Please type *SHOW* to see available projects.", recipient)
                return
                
            project = self.current_projects[idx]
            
            # Use steel requirement from Perplexity if available, otherwise estimate
            steel_req = project.get('steel_requirement') or self._estimate_steel_requirement(project)
            
            message = (
                f"🏗️ *Project Details #{project_num}*\n\n"
                f"*Company:* {project['company']}\n"
                f"*Project:* {project['title']}\n\n"
                f"📅 *Timeline:*\n"
                f"Start: {project.get('start_date', datetime.now()).strftime('%B %Y')}\n"
                f"End: {project.get('end_date', datetime.now()).strftime('%B %Y')}\n\n"
                f"💰 *Contract Value:* Rs. {project.get('value', 0):,.0f} Cr\n"
                f"🏗️ *Est. Steel Requirement:* {steel_req:,.0f} MT\n\n"
                f"🔗 *Source:* {project.get('source_url')}\n\n"
                f"*Options:*\n"
                f"• Type *SAVE #{project_num}* to save this opportunity\n"
                f"• Type *EXCLUDE #{project_num}* to hide it\n"
                f"• Type *MORE* to see more opportunities\n"
                f"• Type *MENU* to return to main menu"
            )
            
            self.twilio.send_whatsapp(message, recipient)
            
        except Exception as e:
            self.logger.error(f"Error sending project details: {str(e)}")
            self.twilio.send_whatsapp("Sorry, something went wrong. Please try again.", recipient)
    
    def _send_filter_options(self, recipient):
        """Send filter options menu"""
        filter_menu = """
*Set Project Value Filters* 💰

Current range: Rs. 20 Lakhs - 100 Crores

Reply with:
• *MIN X* to set minimum value (in Crores)
• *MAX X* to set maximum value (in Crores)
• *RESET* to clear filters

Example: 
Type *MIN 5* to set minimum to 5 Crores
"""
        self.twilio.send_whatsapp(filter_menu, recipient)
    
    def _show_saved_opportunities(self, recipient):
        """Show saved opportunities"""
        if not self.sent_opportunities:
            self.twilio.send_whatsapp("You haven't saved any opportunities yet. Type *SHOW* to see available projects.", recipient)
            return
            
        saved_msg = "*Your Saved Opportunities:*\n\n"
        for idx, project_id in enumerate(self.sent_opportunities[-5:], 1):
            saved_msg += f"{idx}. {project_id.replace('_', ' ').title()}\n"
            
        saved_msg += "\nReply with a number to see details."
        self.twilio.send_whatsapp(saved_msg, recipient)
    
    def _handle_unsubscribe(self, recipient):
        """Handle unsubscribe request"""
        confirm_msg = """
*Are you sure you want to unsubscribe?*

You will no longer receive project updates.

Reply:
• *YES* to confirm unsubscribe
• *NO* to keep receiving updates
"""
        self.twilio.send_whatsapp(confirm_msg, recipient)
    
    def _estimate_steel_requirement(self, project):
        """Estimate steel requirement based on project type and value"""
        try:
            value_in_cr = project.get('value', 0)
            title_lower = project['title'].lower()
            
            if 'metro' in title_lower:
                return value_in_cr * 150  # 150 MT per crore for metro
            elif 'bridge' in title_lower:
                return value_in_cr * 200  # 200 MT per crore for bridges
            elif 'building' in title_lower:
                return value_in_cr * 100  # 100 MT per crore for buildings
            else:
                return value_in_cr * 120  # Default estimation
                
        except Exception as e:
            self.logger.error(f"Error estimating steel requirement: {str(e)}")
            return 0 

    def _format_project_message(self, project, idx):
        """Format a single project message"""
        message = f"*Project #{idx} Details*\n\n"
        
        # Basic info
        message += f"*Company:* {project['company']}\n"
        message += f"*Project:* {project['title']}\n\n"
        
        # Value and timeline
        if project.get('value'):
            message += f"*Value:* ₹{project['value']:.1f} Crore\n"
        
        if project.get('start_date'):
            message += f"*Start Date:* {project['start_date'].strftime('%B %Y')}\n"
        if project.get('end_date'):
            message += f"*End Date:* {project['end_date'].strftime('%B %Y')}\n"
        message += "\n"
        
        # Steel requirements if available
        if project.get('steel_requirements'):
            message += "*Steel Requirements:*\n"
            for steel_type, amount in project['steel_requirements'].items():
                message += f"• {steel_type}: {amount} MT\n"
            message += "\n"
        
        # Add contact information
        if project.get('contacts'):
            message += "*Key Contacts:*\n"
            for contact in project['contacts']:
                message += f"• {contact['name']} - {contact['role']}\n"
                if contact.get('email'):
                    message += f"  Email: {contact['email']}\n"
                if contact.get('phone'):
                    message += f"  Phone: {contact['phone']}\n"
                if contact.get('relationship_notes'):
                    message += f"  Note: {contact['relationship_notes']}\n"
                message += "\n"
        
        # Source and additional info
        if project.get('source_url'):
            message += f"*Source:* {project['source_url']}\n"
        if project.get('description'):
            message += f"\n*Description:*\n{project['description'][:300]}..."
        
        return message 