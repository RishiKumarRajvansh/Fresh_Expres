"""
Advanced Payment Processing Services
Handles multi-gateway payment processing, wallet integration, and UPI payments
"""
import logging
import json
import uuid
import hmac
import hashlib
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Sum, Avg, Q
from django.core.cache import cache
from payments.models_advanced import (
    PaymentGateway, PaymentMethod, PaymentTransaction, PaymentWebhook
)

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """Core payment processing service"""
    
    def __init__(self):
        self.active_gateways = PaymentGateway.objects.filter(is_active=True).order_by('priority')
    
    def select_optimal_gateway(
        self, 
        amount: Decimal, 
        payment_type: str = None, 
        user_location: str = None
    ) -> Optional[PaymentGateway]:
        """Select the best payment gateway based on amount, type, and location"""
        
        suitable_gateways = self.active_gateways.filter(
            min_amount__lte=amount,
            max_amount__gte=amount
        )
        
        # Priority 1: Always prefer PhonePe if available
        phonepe_gateway = suitable_gateways.filter(gateway_type='phonepe').first()
        if phonepe_gateway:
            return phonepe_gateway
        
        # If PhonePe is not available, log warning and return None
        logger.warning("PhonePe gateway not available. No other gateways are currently active.")
        return None
        
        # Legacy code commented out - other gateways disabled
        # # Filter by payment type support
        # if payment_type == 'upi':
        #     suitable_gateways = suitable_gateways.filter(
        #         gateway_type__in=['phonepe']  # Only PhonePe for UPI
        #     )
        # elif payment_type == 'card':
        #     suitable_gateways = suitable_gateways.filter(
        #         gateway_type__in=['phonepe']  # Only PhonePe for cards too
        #     )
        # 
        # # Consider location-based preferences
        # if user_location == 'IN':
        #     indian_gateways = suitable_gateways.filter(
        #         gateway_type__in=['phonepe']  # Only PhonePe for India
        #     )
        #     if indian_gateways.exists():
        #         suitable_gateways = indian_gateways
        # 
        # # Calculate cost for each gateway and select cheapest
        # best_gateway = None
        # lowest_fee = float('inf')
        # 
        # for gateway in suitable_gateways:
        #     fee = gateway.calculate_fee(amount)
        #     if fee < lowest_fee:
        #         lowest_fee = fee
        #         best_gateway = gateway
        # 
        # return best_gateway
    
    def initiate_payment(
        self, 
        order, 
        payment_method: PaymentMethod, 
        amount: Decimal,
        currency: str = 'INR',
        metadata: Dict = None
    ) -> Dict:
        """Initiate a payment transaction"""
        
        if metadata is None:
            metadata = {}
        
        try:
            # Select appropriate gateway
            gateway = self.select_optimal_gateway(
                amount=amount,
                payment_type=payment_method.payment_type,
                user_location='IN'  # Could be dynamic based on user profile
            )
            
            if not gateway:
                return {
                    'success': False,
                    'error': 'No suitable payment gateway available'
                }
            
            # Calculate fees
            gateway_fee = gateway.calculate_fee(amount)
            
            # Create payment transaction
            transaction = PaymentTransaction.objects.create(
                order=order,
                user=order.user,
                payment_method=payment_method,
                gateway=gateway,
                amount=amount,
                gateway_fee=gateway_fee,
                currency=currency,
                expires_at=timezone.now() + timezone.timedelta(minutes=15),
                metadata=metadata
            )
            
            # Get gateway-specific processor
            processor = self._get_gateway_processor(gateway)
            
            # Initiate payment with gateway
            result = processor.create_payment(transaction)
            
            if result['success']:
                transaction.gateway_transaction_id = result.get('transaction_id')
                transaction.status = 'processing'
                transaction.save()
                
                return {
                    'success': True,
                    'transaction_id': str(transaction.transaction_id),
                    'gateway_data': result.get('gateway_data', {}),
                    'redirect_url': result.get('redirect_url'),
                    'payment_url': result.get('payment_url')
                }
            else:
                transaction.mark_failed(
                    error_message=result.get('error'),
                    gateway_response=result.get('response', {})
                )
                
                return {
                    'success': False,
                    'error': result.get('error'),
                    'transaction_id': str(transaction.transaction_id)
                }
        
        except Exception as e:
            logger.error(f"Payment initiation failed: {str(e)}")
            return {
                'success': False,
                'error': 'Payment processing error'
            }
    
    def verify_payment(self, transaction_id: str, gateway_response: Dict) -> Dict:
        """Verify payment with gateway"""
        try:
            transaction = PaymentTransaction.objects.get(transaction_id=transaction_id)
            processor = self._get_gateway_processor(transaction.gateway)
            
            result = processor.verify_payment(transaction, gateway_response)
            
            if result['success']:
                transaction.mark_success(
                    gateway_transaction_id=result.get('gateway_transaction_id'),
                    gateway_response=gateway_response
                )
                
                # Trigger post-payment actions
                self._handle_successful_payment(transaction)
                
                return {
                    'success': True,
                    'transaction_id': str(transaction.transaction_id),
                    'amount': str(transaction.amount)
                }
            else:
                transaction.mark_failed(
                    error_message=result.get('error'),
                    gateway_response=gateway_response
                )
                
                return {
                    'success': False,
                    'error': result.get('error')
                }
        
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'error': 'Transaction not found'
            }
        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            return {
                'success': False,
                'error': 'Payment verification error'
            }
    
    def process_refund(
        self, 
        transaction_id: str, 
        refund_amount: Decimal = None, 
        reason: str = None
    ) -> Dict:
        """Process a refund"""
        try:
            original_transaction = PaymentTransaction.objects.get(
                transaction_id=transaction_id,
                status='success'
            )
            
            # Create refund transaction
            refund_transaction = original_transaction.create_refund(
                refund_amount=refund_amount,
                reason=reason
            )
            
            # Process refund with gateway
            processor = self._get_gateway_processor(original_transaction.gateway)
            result = processor.process_refund(original_transaction, refund_transaction)
            
            if result['success']:
                refund_transaction.mark_success(
                    gateway_transaction_id=result.get('refund_id'),
                    gateway_response=result.get('response', {})
                )
                
                return {
                    'success': True,
                    'refund_transaction_id': str(refund_transaction.transaction_id),
                    'refund_amount': str(refund_transaction.amount)
                }
            else:
                refund_transaction.mark_failed(
                    error_message=result.get('error'),
                    gateway_response=result.get('response', {})
                )
                
                return {
                    'success': False,
                    'error': result.get('error')
                }
        
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'error': 'Original transaction not found'
            }
        except Exception as e:
            logger.error(f"Refund processing failed: {str(e)}")
            return {
                'success': False,
                'error': 'Refund processing error'
            }
    
    def _get_gateway_processor(self, gateway: PaymentGateway):
        """Get gateway-specific processor"""
        processor_classes = {
            'stripe': StripeProcessor,
            'razorpay': RazorpayProcessor,
            'paytm': PaytmProcessor,
            'phonepe': PhonePeProcessor,
            'payu': PayUProcessor,
            'cashfree': CashfreeProcessor,
        }
        
        processor_class = processor_classes.get(gateway.gateway_type, GenericProcessor)
        return processor_class(gateway)
    
    def _handle_successful_payment(self, transaction: PaymentTransaction):
        """Handle post-payment success actions"""
        try:
            # Send payment confirmation notification
            from core.services_notifications import send_order_notification
            send_order_notification(
                order=transaction.order,
                notification_type='order_confirmed',
                context={'payment_amount': str(transaction.amount)}
            )
            
            # Update order status
            transaction.order.status = 'confirmed'
            transaction.order.save()
            
            # Cache successful payment for analytics
            cache.set(
                f'successful_payment_{transaction.id}', 
                {'amount': float(transaction.amount), 'gateway': transaction.gateway.name},
                timeout=3600
            )
            
        except Exception as e:
            logger.error(f"Post-payment processing failed: {str(e)}")


class BaseGatewayProcessor:
    """Base class for gateway processors"""
    
    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway
        self.config = gateway.get_api_config()
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create payment with gateway"""
        raise NotImplementedError
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify payment with gateway"""
        raise NotImplementedError
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process refund with gateway"""
        raise NotImplementedError


class RazorpayProcessor(BaseGatewayProcessor):
    """Razorpay payment processor - COMMENTED OUT"""
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create Razorpay payment - DISABLED"""
        return {
            'success': False,
            'error': 'Razorpay gateway is currently disabled. Only PhonePe is active.'
        }
        
        # # Razorpay implementation commented out
        # try:
        #     import razorpay
        #     
        #     client = razorpay.Client(
        #         auth=(self.config['api_key'], self.config['secret_key'])
        #     )
        #     
        #     order_data = {
        #         'amount': int(transaction.amount * 100),  # Amount in paise
        #         'currency': transaction.currency,
        #         'receipt': str(transaction.transaction_id),
        #         'notes': {
        #             'order_id': str(transaction.order.id),
        #             'user_id': str(transaction.user.id)
        #         }
        #     }
        #     
        #     razorpay_order = client.order.create(data=order_data)
        #     
        #     return {
        #         'success': True,
        #         'transaction_id': razorpay_order['id'],
        #         'gateway_data': {
        #             'order_id': razorpay_order['id'],
        #             'key': self.config['api_key'],
        #             'amount': razorpay_order['amount'],
        #             'currency': razorpay_order['currency'],
    #             'name': 'Fresh Express',
        #             'description': f'Order #{transaction.order.id}',
        #             'prefill': {
        #                 'name': transaction.user.get_full_name(),
        #                 'email': transaction.user.email,
        #                 'contact': getattr(transaction.user.profile, 'phone', '') if hasattr(transaction.user, 'profile') else ''
        #             },
        #             'theme': {
        #                 'color': '#d32f2f'
        #             }
        #         }
        #     }
        # 
        # except Exception as e:
        #     logger.error(f"Razorpay order creation failed: {str(e)}")
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify Razorpay payment - DISABLED"""
        return {
            'success': False,
            'error': 'Razorpay gateway is currently disabled. Only PhonePe is active.'
        }
        
        # # Razorpay verification commented out
        # try:
        #     import razorpay
        #     
        #     client = razorpay.Client(
        #         auth=(self.config['api_key'], self.config['secret_key'])
        #     )
        #     
        #     # Verify signature
        #     params_dict = {
        #         'razorpay_order_id': response.get('razorpay_order_id'),
        #         'razorpay_payment_id': response.get('razorpay_payment_id'),
        #         'razorpay_signature': response.get('razorpay_signature')
        #     }
        #     
        #     client.utility.verify_payment_signature(params_dict)
        #     
        #     # Fetch payment details
        #     payment_id = response.get('razorpay_payment_id')
        #     payment = client.payment.fetch(payment_id)
        #     
        #     if payment['status'] == 'captured':
        #         return {
        #             'success': True,
        #             'gateway_transaction_id': payment_id,
        #             'response': payment
        #         }
        #     else:
        #         return {
        #             'success': False,
        #             'error': f"Payment status: {payment['status']}"
        #         }
        # 
        # except Exception as e:
        #     logger.error(f"Razorpay verification failed: {str(e)}")
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process Razorpay refund - DISABLED"""
        return {
            'success': False,
            'error': 'Razorpay gateway is currently disabled. Only PhonePe is active.'
        }
        
        # # Razorpay refund commented out
        # try:
        #     import razorpay
        #     
        #     client = razorpay.Client(
        #         auth=(self.config['api_key'], self.config['secret_key'])
        #     )
        #     
        #     refund_data = {
        #         'amount': int(refund.amount * 100),  # Amount in paise
        #         'notes': {
        #             'refund_reason': refund.metadata.get('reason', 'Customer refund'),
        #             'original_transaction': str(original.transaction_id)
        #         }
        #     }
        #     
        #     razorpay_refund = client.payment.refund(
        #         original.gateway_transaction_id, 
        #         refund_data
        #     )
        #     
        #     return {
        #         'success': True,
        #         'refund_id': razorpay_refund['id'],
        #         'response': razorpay_refund
        #     }
        # 
        # except Exception as e:
        #     logger.error(f"Razorpay refund failed: {str(e)}")
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }


class StripeProcessor(BaseGatewayProcessor):
    """Stripe payment processor - COMMENTED OUT"""
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create Stripe payment - DISABLED"""
        return {
            'success': False,
            'error': 'Stripe gateway is currently disabled. Only PhonePe is active.'
        }
        
        # # Stripe implementation commented out
        # try:
        #     import stripe
        #     
        #     stripe.api_key = self.config['secret_key']
        #     
        #     intent = stripe.PaymentIntent.create(
        #         amount=int(transaction.amount * 100),  # Amount in cents
        #         currency=transaction.currency.lower(),
        #         metadata={
        #             'order_id': str(transaction.order.id),
        #             'transaction_id': str(transaction.transaction_id)
        #         },
        #         automatic_payment_methods={'enabled': True}
        #     )
        #     
        #     return {
        #         'success': True,
        #         'transaction_id': intent.id,
        #         'gateway_data': {
        #             'client_secret': intent.client_secret,
        #             'publishable_key': self.config['api_key']
        #         }
        #     }
        # 
        # except Exception as e:
        #     logger.error(f"Stripe payment intent creation failed: {str(e)}")
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify Stripe payment - DISABLED"""
        return {
            'success': False,
            'error': 'Stripe gateway is currently disabled. Only PhonePe is active.'
        }
        
        # # Stripe verification commented out
        # try:
        #     import stripe
        #     
        #     stripe.api_key = self.config['secret_key']
        #     
        #     payment_intent_id = response.get('payment_intent')
        #     intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        #     
        #     if intent.status == 'succeeded':
        #         return {
        #             'success': True,
        #             'gateway_transaction_id': intent.id,
        #             'response': dict(intent)
        #         }
        #     else:
        #         return {
        #             'success': False,
        #             'error': f"Payment status: {intent.status}"
        #         }
        # 
        # except Exception as e:
        #     logger.error(f"Stripe verification failed: {str(e)}")
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process Stripe refund - DISABLED"""
        return {
            'success': False,
            'error': 'Stripe gateway is currently disabled. Only PhonePe is active.'
        }
        
        # # Stripe refund commented out
        # try:
        #     import stripe
        #     
        #     stripe.api_key = self.config['secret_key']
        #     
        #     stripe_refund = stripe.Refund.create(
        #         payment_intent=original.gateway_transaction_id,
        #         amount=int(refund.amount * 100),
        #         metadata={
        #             'reason': refund.metadata.get('reason', 'requested_by_customer'),
        #             'original_transaction': str(original.transaction_id)
        #         }
        #     )
        #     
        #     return {
        #         'success': True,
        #         'refund_id': stripe_refund.id,
        #         'response': dict(stripe_refund)
        #     }
        # 
        # except Exception as e:
        #     logger.error(f"Stripe refund failed: {str(e)}")
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }


class PaytmProcessor(BaseGatewayProcessor):
    """Paytm payment processor - COMMENTED OUT"""
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create Paytm payment - DISABLED"""
        return {
            'success': False,
            'error': 'Paytm gateway is currently disabled. Only PhonePe is active.'
        }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify Paytm payment - DISABLED"""
        return {
            'success': False,
            'error': 'Paytm gateway is currently disabled. Only PhonePe is active.'
        }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process Paytm refund - DISABLED"""
        return {
            'success': False,
            'error': 'Paytm gateway is currently disabled. Only PhonePe is active.'
        }


class PhonePeProcessor(BaseGatewayProcessor):
    """PhonePe payment processor"""
    
    def __init__(self, gateway: PaymentGateway):
        super().__init__(gateway)
        self.merchant_id = self.config.get('merchant_id')
        self.salt_key = self.config.get('salt_key')
        self.salt_index = self.config.get('salt_index', 1)
        self.base_url = self.config.get('base_url', 'https://api-preprod.phonepe.com/apis/pg-sandbox')
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create PhonePe payment"""
        try:
            import base64
            import requests
            
            # Create transaction ID
            merchant_transaction_id = f"MT{transaction.transaction_id}"
            
            # Prepare payment request
            payload = {
                "merchantId": self.merchant_id,
                "merchantTransactionId": merchant_transaction_id,
                "merchantUserId": f"MU{transaction.user.id}",
                "amount": int(transaction.amount * 100),  # Amount in paise
                "redirectUrl": f"{settings.SITE_URL}/payments/phonepe/callback/",
                "redirectMode": "POST",
                "callbackUrl": f"{settings.SITE_URL}/payments/phonepe/webhook/",
                "mobileNumber": getattr(transaction.user.profile, 'phone', '') if hasattr(transaction.user, 'profile') else '',
                "paymentInstrument": {
                    "type": "PAY_PAGE"
                }
            }
            
            # Encode payload
            payload_json = json.dumps(payload)
            payload_b64 = base64.b64encode(payload_json.encode()).decode()
            
            # Create checksum
            string_to_hash = f"{payload_b64}/pg/v1/pay{self.salt_key}"
            checksum = hashlib.sha256(string_to_hash.encode()).hexdigest() + "###" + str(self.salt_index)
            
            # Prepare request headers
            headers = {
                'Content-Type': 'application/json',
                'X-VERIFY': checksum
            }
            
            # Make API request
            url = f"{self.base_url}/pg/v1/pay"
            response = requests.post(
                url,
                json={"request": payload_b64},
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('success'):
                payment_url = response_data['data']['instrumentResponse']['redirectInfo']['url']
                
                return {
                    'success': True,
                    'transaction_id': merchant_transaction_id,
                    'payment_url': payment_url,
                    'gateway_data': {
                        'merchant_transaction_id': merchant_transaction_id,
                        'phonepe_transaction_id': response_data.get('data', {}).get('transactionId'),
                        'payment_url': payment_url
                    }
                }
            else:
                error_message = response_data.get('message', 'PhonePe payment initiation failed')
                logger.error(f"PhonePe payment failed: {error_message}")
                return {
                    'success': False,
                    'error': error_message
                }
                
        except requests.RequestException as e:
            logger.error(f"PhonePe API request failed: {str(e)}")
            return {
                'success': False,
                'error': 'Payment gateway communication error'
            }
        except Exception as e:
            logger.error(f"PhonePe payment creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify PhonePe payment"""
        try:
            import base64
            import requests
            
            # Get merchant transaction ID from response or transaction metadata
            merchant_transaction_id = response.get('merchantTransactionId') or response.get('transactionId')
            if not merchant_transaction_id:
                # Try to construct from transaction ID
                merchant_transaction_id = f"MT{transaction.transaction_id}"
            
            # Create checksum for status check
            string_to_hash = f"/pg/v1/status/{self.merchant_id}/{merchant_transaction_id}{self.salt_key}"
            checksum = hashlib.sha256(string_to_hash.encode()).hexdigest() + "###" + str(self.salt_index)
            
            # Prepare request headers
            headers = {
                'Content-Type': 'application/json',
                'X-VERIFY': checksum,
                'X-MERCHANT-ID': self.merchant_id
            }
            
            # Make status check API request
            url = f"{self.base_url}/pg/v1/status/{self.merchant_id}/{merchant_transaction_id}"
            status_response = requests.get(url, headers=headers, timeout=30)
            status_data = status_response.json()
            
            if status_response.status_code == 200 and status_data.get('success'):
                payment_data = status_data.get('data', {})
                payment_state = payment_data.get('state')
                
                if payment_state == 'COMPLETED':
                    return {
                        'success': True,
                        'gateway_transaction_id': payment_data.get('transactionId'),
                        'response': payment_data
                    }
                elif payment_state == 'FAILED':
                    return {
                        'success': False,
                        'error': payment_data.get('responseCodeDescription', 'Payment failed')
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Payment in {payment_state} state"
                    }
            else:
                error_message = status_data.get('message', 'Payment verification failed')
                logger.error(f"PhonePe verification failed: {error_message}")
                return {
                    'success': False,
                    'error': error_message
                }
                
        except requests.RequestException as e:
            logger.error(f"PhonePe verification API error: {str(e)}")
            return {
                'success': False,
                'error': 'Payment verification communication error'
            }
        except Exception as e:
            logger.error(f"PhonePe verification failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process PhonePe refund"""
        try:
            import base64
            import requests
            
            # Create refund transaction ID
            merchant_refund_id = f"RF{refund.transaction_id}"
            original_transaction_id = f"MT{original.transaction_id}"
            
            # Prepare refund request
            payload = {
                "merchantId": self.merchant_id,
                "merchantUserId": f"MU{original.user.id}",
                "originalTransactionId": original_transaction_id,
                "merchantTransactionId": merchant_refund_id,
                "amount": int(refund.amount * 100),  # Amount in paise
                "callbackUrl": f"{settings.SITE_URL}/payments/phonepe/refund-webhook/"
            }
            
            # Encode payload
            payload_json = json.dumps(payload)
            payload_b64 = base64.b64encode(payload_json.encode()).decode()
            
            # Create checksum
            string_to_hash = f"{payload_b64}/pg/v1/refund{self.salt_key}"
            checksum = hashlib.sha256(string_to_hash.encode()).hexdigest() + "###" + str(self.salt_index)
            
            # Prepare request headers
            headers = {
                'Content-Type': 'application/json',
                'X-VERIFY': checksum
            }
            
            # Make refund API request
            url = f"{self.base_url}/pg/v1/refund"
            response = requests.post(
                url,
                json={"request": payload_b64},
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('success'):
                return {
                    'success': True,
                    'refund_id': merchant_refund_id,
                    'response': response_data.get('data', {})
                }
            else:
                error_message = response_data.get('message', 'PhonePe refund failed')
                logger.error(f"PhonePe refund failed: {error_message}")
                return {
                    'success': False,
                    'error': error_message
                }
                
        except requests.RequestException as e:
            logger.error(f"PhonePe refund API error: {str(e)}")
            return {
                'success': False,
                'error': 'Refund gateway communication error'
            }
        except Exception as e:
            logger.error(f"PhonePe refund failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class PayUProcessor(BaseGatewayProcessor):
    """PayU payment processor - COMMENTED OUT"""
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create PayU payment - DISABLED"""
        return {
            'success': False,
            'error': 'PayU gateway is currently disabled. Only PhonePe is active.'
        }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify PayU payment - DISABLED"""
        return {
            'success': False,
            'error': 'PayU gateway is currently disabled. Only PhonePe is active.'
        }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process PayU refund - DISABLED"""
        return {
            'success': False,
            'error': 'PayU gateway is currently disabled. Only PhonePe is active.'
        }


class CashfreeProcessor(BaseGatewayProcessor):
    """Cashfree payment processor - COMMENTED OUT"""
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        """Create Cashfree payment - DISABLED"""
        return {
            'success': False,
            'error': 'Cashfree gateway is currently disabled. Only PhonePe is active.'
        }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        """Verify Cashfree payment - DISABLED"""
        return {
            'success': False,
            'error': 'Cashfree gateway is currently disabled. Only PhonePe is active.'
        }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        """Process Cashfree refund - DISABLED"""
        return {
            'success': False,
            'error': 'Cashfree gateway is currently disabled. Only PhonePe is active.'
        }


class GenericProcessor(BaseGatewayProcessor):
    """Generic processor for unsupported gateways"""
    
    def create_payment(self, transaction: PaymentTransaction) -> Dict:
        return {
            'success': False,
            'error': 'Gateway not supported'
        }
    
    def verify_payment(self, transaction: PaymentTransaction, response: Dict) -> Dict:
        return {
            'success': False,
            'error': 'Gateway not supported'
        }
    
    def process_refund(self, original: PaymentTransaction, refund: PaymentTransaction) -> Dict:
        return {
            'success': False,
            'error': 'Gateway not supported'
        }


class PaymentAnalyticsService:
    """Service for payment analytics and reporting"""
    
    @staticmethod
    def generate_daily_analytics(date=None):
        """Generate daily payment analytics"""
        if date is None:
            date = timezone.now().date()
        
        from payments.models_advanced import PaymentAnalytics
        from django.db.models import Count, Sum, Avg, Q
        
        # Process analytics for each gateway
        for gateway in PaymentGateway.objects.filter(is_active=True):
            transactions = PaymentTransaction.objects.filter(
                gateway=gateway,
                initiated_at__date=date
            )
            
            total_count = transactions.count()
            successful_count = transactions.filter(status='success').count()
            failed_count = transactions.filter(status='failed').count()
            
            # Calculate amounts
            amounts = transactions.filter(status='success').aggregate(
                total_amount=Sum('amount'),
                total_fees=Sum('gateway_fee')
            )
            
            total_amount = amounts['total_amount'] or Decimal('0.00')
            total_fees = amounts['total_fees'] or Decimal('0.00')
            
            # Payment method breakdown
            payment_methods = transactions.values('payment_method__payment_type').annotate(
                count=Count('id')
            )
            
            method_counts = {}
            for pm in payment_methods:
                method_counts[pm['payment_method__payment_type']] = pm['count']
            
            # Create or update analytics record
            analytics, created = PaymentAnalytics.objects.update_or_create(
                date=date,
                gateway=gateway,
                defaults={
                    'total_transactions': total_count,
                    'successful_transactions': successful_count,
                    'failed_transactions': failed_count,
                    'total_amount': total_amount,
                    'successful_amount': total_amount,
                    'total_fees': total_fees,
                    'card_transactions': method_counts.get('card', 0),
                    'upi_transactions': method_counts.get('upi', 0),
                    'wallet_transactions': method_counts.get('wallet', 0),
                    'netbanking_transactions': method_counts.get('netbanking', 0),
                    'cod_transactions': method_counts.get('cod', 0),
                }
            )
            
            # Calculate rates
            analytics.calculate_metrics()
    
    @staticmethod
    def get_gateway_performance(days=30):
        """Get gateway performance comparison"""
        from datetime import timedelta
        from payments.models_advanced import PaymentAnalytics
        from django.db.models import Sum, Avg
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        performance = PaymentAnalytics.objects.filter(
            date__range=[start_date, end_date]
        ).values('gateway__name', 'gateway__gateway_type').annotate(
            total_transactions=Sum('total_transactions'),
            successful_transactions=Sum('successful_transactions'),
            total_amount=Sum('successful_amount'),
            total_fees=Sum('total_fees'),
            avg_success_rate=Avg('success_rate'),
            avg_transaction_value=Avg('average_transaction_value')
        ).order_by('-total_amount')
        
        return list(performance)
    
    @staticmethod
    def detect_fraud_patterns():
        """Detect potential fraud patterns in payments"""
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=1)
        
        # Multiple failed attempts from same user
        suspicious_users = PaymentTransaction.objects.filter(
            initiated_at__gte=cutoff_time,
            status='failed'
        ).values('user').annotate(
            failed_count=Count('id')
        ).filter(failed_count__gte=5)
        
        # High-value transactions
        high_value_transactions = PaymentTransaction.objects.filter(
            initiated_at__gte=cutoff_time,
            amount__gte=Decimal('10000.00')
        )
        
        return {
            'suspicious_users': list(suspicious_users),
            'high_value_transactions': list(high_value_transactions.values())
        }
