from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
from config.settings import Config
from datetime import datetime, timedelta
import time

class WhatsAppHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize Twilio client if configuration exists
        if all([Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN, Config.WHATSAPP_FROM, Config.WHATSAPP_TO]):
            try:
                self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
                self.whatsapp_from = Config.WHATSAPP_FROM
                self.recipients = Config.WHATSAPP_TO
                self.enabled = True
                self.logger.info("WhatsApp notifications enabled")
            except Exception as e:
                self.logger.error(f"Failed to initialize Twilio client: {str(e)}")
                self.enabled = False
        else:
            self.enabled = False
            self.logger.info("WhatsApp notifications disabled (missing configuration)")
    
    def send_project_opportunities(self, projects):
        """Send project opportunities via WhatsApp"""
        if not self.enabled or not projects:
            return False
            
        success = True
        for recipient in self.recipients:
            try:
                # Format recipient number
                to_number = recipient.strip().strip('+')
                
                # Send overview message first
                overview = f"🏗️ *New Project Opportunities*\n\nFound {len(projects)} new projects:\n"
                for idx, project in enumerate(projects, 1):
                    overview += f"\n{idx}. {project['company']} - {project['title']}"
                    if project.get('value'):
                        overview += f" (₹{project['value']:.1f} Cr)"
                
                if not self._send_whatsapp(overview, to_number):
                    success = False
                    continue
                
                # Send detailed messages for each project
                for idx, project in enumerate(projects, 1):
                    message = self._format_project_message(project, idx)
                    if not self._send_whatsapp(message, to_number):
                        success = False
                        break
                    time.sleep(1)  # Add delay between messages
                    
            except Exception as e:
                self.logger.error(f"Error sending WhatsApp to {recipient}: {str(e)}")
                success = False
                
        return success
    
    def _format_project_message(self, project, idx=1):
        """Format a project for WhatsApp message"""
        try:
            # Basic project info
            message = f"*Project #{idx}*\n\n"
            message += f"🏢 *Company:* {project.get('company', 'N/A')}\n"
            message += f"📋 *Title:* {project.get('title', 'N/A')}\n\n"
            
            # Timeline
            start_date = project.get('start_date', datetime.now()).strftime('%B %Y')
            end_date = project.get('end_date', datetime.now() + timedelta(days=365)).strftime('%B %Y')
            message += f"📅 *Timeline:* {start_date} - {end_date}\n"
            
            # Value and requirements
            if project.get('value'):
                message += f"💰 *Value:* ₹{project.get('value', 0):,.0f} Cr\n"
                
            steel_reqs = project.get('steel_requirements', {})
            if steel_reqs:
                message += "\n⚙️ *Steel Requirements:*\n"
                if 'primary' in steel_reqs:
                    message += f"• Primary: {steel_reqs['primary'].get('type', 'N/A')} ({steel_reqs['primary'].get('quantity', 0):,} MT)\n"
                if 'secondary' in steel_reqs and steel_reqs['secondary']:
                    for req in steel_reqs['secondary']:
                        if req.get('quantity', 0) > 0:
                            message += f"• Secondary: {req.get('type', 'N/A')} ({req.get('quantity', 0):,} MT)\n"
                if 'total' in steel_reqs:
                    message += f"• Total: {steel_reqs.get('total', 0):,} MT\n"
            
            # Source link
            if project.get('source_url'):
                message += f"\n🔗 *Source:* {project.get('source_url')}"
                
            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting WhatsApp message: {str(e)}")
            return "Error formatting project message"
    
    def _send_whatsapp(self, message, to_number, max_retries=3):
        """Send WhatsApp message with retries"""
        if not self.enabled:
            return False
            
        for attempt in range(max_retries):
            try:
                # Format WhatsApp numbers
                from_number = self.whatsapp_from.strip('+')
                
                # Send message
                response = self.client.messages.create(
                    from_=f"whatsapp:+{from_number}",
                    body=message,
                    to=f"whatsapp:+{to_number}"
                )
                
                self.logger.info(f"Sent WhatsApp message to {to_number} (SID: {response.sid})")
                return True
                
            except TwilioRestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to send WhatsApp to {to_number} after {max_retries} attempts: {str(e)}")
                else:
                    self.logger.warning(f"Attempt {attempt + 1} failed for {to_number}, retrying in 2 seconds...")
                    time.sleep(2)  # Wait before retry
                    continue
            except Exception as e:
                self.logger.error(f"Unexpected error sending WhatsApp to {to_number}: {str(e)}")
                return False
                
        return False 