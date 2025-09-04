"""
OTP Service for Order Handover System
Handles OTP generation, verification for Store->Agent and Agent->Customer handovers
"""

import random
import string
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class OTPService:
    """Service to handle OTP generation and verification for order handovers"""
    
    @staticmethod
    def generate_otp():
        """Generate a 4-digit OTP"""
        return ''.join(random.choices(string.digits, k=4))
    
    @staticmethod
    def create_store_handover_otp(order):
        """Create OTP for store->agent handover"""
        otp = OTPService.generate_otp()
        cache_key = f"store_handover_otp_{order.order_number}"
        
        # Store OTP in cache for 30 minutes
        cache.set(cache_key, {
            'otp': otp,
            'created_at': timezone.now().isoformat(),
            'order_id': str(order.order_id),
            'type': 'store_handover'
        }, timeout=1800)  # 30 minutes
        
        logger.info(f"Store handover OTP generated for order {order.order_number}: {otp}")
        
        # TODO: Send OTP to store staff via SMS/notification
        return otp
    
    @staticmethod
    def verify_store_handover_otp(order, otp_entered):
        """Verify store handover OTP"""
        cache_key = f"store_handover_otp_{order.order_number}"
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            return False, "OTP expired or not found"
        
        if otp_data['otp'] != otp_entered:
            return False, "Invalid OTP"
        
        # Mark as verified and remove from cache
        cache.delete(cache_key)
        
        # Update order status
        if hasattr(order, 'delivery_assignment'):
            assignment = order.delivery_assignment
            assignment.status = 'picked_up'
            assignment.picked_up_at = timezone.now()
            assignment.save()
            
            order.status = 'out_for_delivery' 
            order.store_handover_confirmed = True
            order.store_handover_time = timezone.now()
            order.save()
        
        logger.info(f"Store handover OTP verified for order {order.order_number}")
        return True, "Store handover confirmed"
    
    @staticmethod
    def create_customer_delivery_otp(order):
        """Create OTP for agent->customer delivery"""
        otp = OTPService.generate_otp()
        cache_key = f"customer_delivery_otp_{order.order_number}"
        
        # Store OTP in cache for 60 minutes
        cache.set(cache_key, {
            'otp': otp,
            'created_at': timezone.now().isoformat(),
            'order_id': str(order.order_id),
            'type': 'customer_delivery'
        }, timeout=3600)  # 60 minutes
        
        logger.info(f"Customer delivery OTP generated for order {order.order_number}: {otp}")
        
        # TODO: Send OTP to customer via SMS/notification
        return otp
    
    @staticmethod
    def verify_customer_delivery_otp(order, otp_entered):
        """Verify customer delivery OTP"""
        cache_key = f"customer_delivery_otp_{order.order_number}"
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            return False, "OTP expired or not found"
        
        if otp_data['otp'] != otp_entered:
            return False, "Invalid OTP"
        
        # Mark as verified and remove from cache
        cache.delete(cache_key)
        
        # Update order and assignment status
        if hasattr(order, 'delivery_assignment'):
            assignment = order.delivery_assignment
            assignment.status = 'delivered'
            assignment.delivered_at = timezone.now()
            
            # Calculate actual delivery time
            if assignment.picked_up_at:
                time_diff = timezone.now() - assignment.picked_up_at
                assignment.actual_time_minutes = int(time_diff.total_seconds() / 60)
            
            assignment.save()
            
            order.status = 'delivered'
            order.customer_delivery_confirmed = True
            order.customer_delivery_time = timezone.now()
            order.save()
        
        logger.info(f"Customer delivery OTP verified for order {order.order_number}")
        return True, "Delivery confirmed successfully"
    
    @staticmethod
    def get_otp_status(order, otp_type):
        """Get current OTP status for an order"""
        cache_key = f"{otp_type}_otp_{order.order_number}"
        otp_data = cache.get(cache_key)
        
        if otp_data:
            created_at = timezone.fromisoformat(otp_data['created_at'])
            expires_at = created_at + timedelta(minutes=30 if otp_type == 'store_handover' else 60)
            
            return {
                'exists': True,
                'otp': otp_data['otp'],
                'created_at': created_at,
                'expires_at': expires_at,
                'expired': timezone.now() > expires_at
            }
        
        return {'exists': False}
    
    @staticmethod
    def simulate_sms_send(phone_number, otp, message_type):
        """Simulate SMS sending (replace with actual SMS service)"""
        messages = {
            'store_handover': f'Fresh Express: Your store handover OTP is {otp}. Valid for 30 minutes.',
            'customer_delivery': f'Fresh Express: Your delivery OTP is {otp}. Valid for 60 minutes.'
        }
        
        message = messages.get(message_type, f'Your OTP is {otp}')
        
        # TODO: Integrate with actual SMS service (Twilio, AWS SNS, etc.)
        logger.info(f"SMS sent to {phone_number}: {message}")
        
        return True
