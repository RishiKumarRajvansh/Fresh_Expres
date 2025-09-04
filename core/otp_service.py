import random
import logging
from django.conf import settings
from django.core.cache import cache
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

logger = logging.getLogger(__name__)

class OTPService:
    """Handle OTP generation and verification via Twilio Verify Service"""
    
    def __init__(self):
        self.client = None
        self.verify_service_sid = None
        self.development_mode = True
        
        if (settings.TWILIO_ACCOUNT_SID and 
            settings.TWILIO_AUTH_TOKEN and 
            settings.TWILIO_VERIFY_SERVICE_SID):
            try:
                self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                self.verify_service_sid = settings.TWILIO_VERIFY_SERVICE_SID
                self.development_mode = False
                logger.info("Twilio Verify service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                self.development_mode = True
        else:
            logger.info("Twilio Verify not configured, running in development mode")
    
    def normalize_phone_number(self, phone_number):
        """Normalize phone number format for Twilio"""
        # Remove any spaces, dashes, or special characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if not present
        if len(cleaned) == 10 and cleaned.startswith('8'):  # Indian mobile numbers starting with 8/9
            cleaned = '+91' + cleaned
        elif len(cleaned) == 10 and cleaned.startswith('9'):
            cleaned = '+91' + cleaned
        elif not cleaned.startswith('+'):
            cleaned = '+91' + cleaned
        else:
            cleaned = '+' + cleaned.lstrip('+')
            
        logger.info(f"Normalized phone: {phone_number} -> {cleaned}")
        return cleaned
    
    def send_otp_to_phone(self, phone_number):
        """Send OTP using Twilio Verify service"""
        # For consistency, use the original phone number for cache key in dev mode
        cache_phone = phone_number  # Keep original format for cache
        normalized_phone = self.normalize_phone_number(phone_number)
        
        if self.development_mode:
            # Development mode - generate and cache OTP manually
            otp = str(random.randint(100000, 999999))
            cache_key = f"dev_otp_{cache_phone}"  # Use original phone format
            cache.set(cache_key, otp, timeout=300)  # 5 minutes
            logger.info(f"[DEV MODE] Generated OTP {otp} for {cache_phone} (normalized: {normalized_phone})")
            return True, f"OTP sent successfully (DEV MODE): {otp}"
        
        try:
            verification = self.client.verify.v2.services(self.verify_service_sid).verifications.create(
                to=normalized_phone, 
                channel='sms'
            )
            logger.info(f"Twilio Verify OTP sent to {normalized_phone}. SID: {verification.sid}")
            return True, "OTP sent successfully via SMS"
            
        except TwilioException as e:
            error_message = str(e)
            logger.error(f"Twilio Verify error for {normalized_phone}: {e}")
            
            # Check if it's a trial account limitation (unverified number)
            if "unverified" in error_message.lower() or "trial" in error_message.lower():
                # Fallback to development mode for unverified numbers
                otp = str(random.randint(100000, 999999))
                cache_key = f"dev_otp_{cache_phone}"
                cache.set(cache_key, otp, timeout=300)  # 5 minutes
                logger.info(f"[TRIAL FALLBACK] Generated OTP {otp} for {cache_phone} due to Twilio trial limitation")
                return True, f"OTP sent successfully (Trial Mode - use this OTP): {otp}"
            
            return False, f"Failed to send OTP: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error sending OTP to {normalized_phone}: {e}")
            return False, "Failed to send OTP"
    
    def verify_otp(self, phone_number, submitted_otp):
        """Verify OTP using Twilio Verify service"""
        # For consistency, use the original phone number for cache key in dev mode
        cache_phone = phone_number  # Keep original format for cache
        normalized_phone = self.normalize_phone_number(phone_number)
        
        # First check if we have a local cache entry (development mode or trial fallback)
        cache_key = f"dev_otp_{cache_phone}"
        stored_otp = cache.get(cache_key)
        
        if stored_otp:
            # Local verification (development mode or trial fallback)
            logger.info(f"[LOCAL VERIFY] Verifying OTP for {cache_phone} (normalized: {normalized_phone})")
            logger.info(f"Submitted: {submitted_otp}, Stored: {stored_otp}")
            
            if submitted_otp == stored_otp:
                cache.delete(cache_key)
                logger.info(f"[LOCAL VERIFY] OTP verified successfully for {cache_phone}")
                return True, "OTP verified successfully"
            else:
                return False, "Invalid OTP"
        
        if self.development_mode:
            return False, "OTP expired or not found"
        
        try:
            verification_check = self.client.verify.v2.services(self.verify_service_sid).verification_checks.create(
                to=normalized_phone,
                code=submitted_otp
            )
            
            if verification_check.status == 'approved':
                logger.info(f"Twilio Verify OTP approved for {normalized_phone}")
                return True, "OTP verified successfully"
            else:
                logger.warning(f"Twilio Verify OTP failed for {normalized_phone}: {verification_check.status}")
                return False, "Invalid or expired OTP"
                
        except TwilioException as e:
            logger.error(f"Twilio Verify error for {normalized_phone}: {e}")
            return False, f"Verification failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected verification error for {normalized_phone}: {e}")
            return False, "Verification failed"
    
    # Legacy methods for backwards compatibility (not used with Verify service)
    def generate_otp(self, phone_number):
        """Legacy method - use send_otp_to_phone instead"""
        return str(random.randint(100000, 999999))
    
    def send_otp(self, phone_number, otp):
        """Legacy method - use send_otp_to_phone instead"""
        return True, "Use send_otp_to_phone method"

# Global instance
otp_service = OTPService()
