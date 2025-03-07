from twilio.rest import Client # type: ignore
from twilio.base.exceptions import TwilioRestException # type: ignore
from config.settings import Config
import logging
import json

class TwilioClient:
    MAX_LENGTH = 1500  # WhatsApp message limit with some buffer
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        try:
            self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            self.logger.info("Successfully initialized Twilio client")
        except Exception as e:
            self.logger.error(f"Failed to initialize Twilio client: {str(e)}")
            raise
        
    def send_whatsapp(self, message):
        """Send WhatsApp message, splitting into multiple parts if too long"""
        success = True
        self.logger.info(f"Attempting to send message to {len(Config.WHATSAPP_TO)} recipients")
        
        # Split message if too long
        messages = self._split_message(message)
        total_parts = len(messages)
        
        for recipient in Config.WHATSAPP_TO:
            try:
                self.logger.info(f"Sending to {recipient}...")
                
                # Send each part
                for idx, msg_part in enumerate(messages, 1):
                    if total_parts > 1:
                        msg_part = f"(Part {idx}/{total_parts})\n\n{msg_part}"
                    
                    # Ensure the WhatsApp number format is correct
                    from_number = Config.WHATSAPP_FROM.strip('+')  # Remove + if present
                    to_number = recipient.strip().strip('+')  # Remove + and whitespace
                    
                    response = self.client.messages.create(
                        from_=f"whatsapp:+{from_number}",
                        content_sid='HXb5b62575e6e4ff6129ad7c8efe1f983e',
                        content_variables=json.dumps({"1": msg_part}),
                        to=f"whatsapp:+{to_number}"
                    )
                    self.logger.info(f"Successfully sent part {idx}/{total_parts} to {recipient} (SID: {response.sid})")
                    
            except TwilioRestException as e:
                self.logger.error(f"Twilio error sending to {recipient}: {str(e)}")
                success = False
            except Exception as e:
                self.logger.error(f"Unexpected error sending to {recipient}: {str(e)}", exc_info=True)
                success = False
                
        return success
    
    def _split_message(self, message):
        """Split message into parts if it exceeds maximum length"""
        if len(message) <= self.MAX_LENGTH:
            return [message]
            
        parts = []
        lines = message.split('\n')
        current_part = ""
        
        # Try to split at logical break points
        for line in lines:
            if len(current_part) + len(line) + 1 <= self.MAX_LENGTH:
                current_part += line + '\n'
            else:
                # If current part is not empty, add it to parts
                if current_part:
                    parts.append(current_part.strip())
                current_part = line + '\n'
        
        # Add the last part if not empty
        if current_part:
            parts.append(current_part.strip())
            
        return parts