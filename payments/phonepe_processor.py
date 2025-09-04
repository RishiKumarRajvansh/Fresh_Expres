"""
PhonePe Payment Processor
Based on official PhonePe API documentation
"""
import requests
import json
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models_advanced import PaymentGateway, PaymentTransaction


class PhonePeProcessor:
    """PhonePe Payment Gateway Processor following official API"""
    
    def __init__(self):
        """Initialize PhonePe processor with configuration"""
        self.gateway = PaymentGateway.objects.get(gateway_type='phonepe', is_active=True)
        config = self.gateway.get_api_config()
        
        self.merchant_id = config['merchant_id']
        self.client_id = config['merchant_id']  # In PhonePe, client_id is same as merchant_id
        self.client_secret = config['salt_key']
        self.salt_index = int(config['salt_index'])
        self.base_url = config['base_url']
        
        # OAuth endpoints
        self.auth_url = f"{self.base_url}/v1/oauth/token"
        self.payment_url = f"{self.base_url}/checkout/v2/pay"
        self.status_url = f"{self.base_url}/checkout/v2/order"
        
        self._auth_token = None
        self._token_expires_at = None
    
    def get_auth_token(self):
        """Get or refresh OAuth token"""
        try:
            # Check if token is still valid
            if self._auth_token and self._token_expires_at:
                current_time = timezone.now().timestamp()
                if current_time < (self._token_expires_at - Decimal('300')):  # Refresh 5 minutes before expiry
                    return self._auth_token
            
            # Request new token
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            data = {
                'client_id': self.client_id,
                'client_version': '1.0',  # Default version
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(self.auth_url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self._auth_token = token_data.get('access_token')
                self._token_expires_at = token_data.get('expires_at')
                return self._auth_token
            else:
                return None
                
        except Exception as e:
            return None
    
    def create_payment(self, amount, order_id, user_id, redirect_url, callback_url=None):
        """Create payment request with PhonePe"""
        try:
            # Get auth token
            auth_token = self.get_auth_token()
            if not auth_token:
                return {
                    'success': False,
                    'error': 'Authentication failed with PhonePe'
                }
            
            # Convert amount to paisa (PhonePe expects amount in paisa)
            amount_paisa = int(float(amount) * 100)
            
            # Create payment payload - only enable PhonePe UPI options
            payload = {
                "merchantOrderId": str(order_id),
                "amount": amount_paisa,
                "paymentFlow": {
                    "type": "PG_CHECKOUT",
                    "message": f"Payment for Order {order_id}",
                    "merchantUrls": {
                        "redirectUrl": redirect_url
                    },
                    "paymentModeConfig": {
                        "enabledPaymentModes": [
                            {
                                "type": "UPI_INTENT"
                            },
                            {
                                "type": "UPI_COLLECT"
                            },
                            {
                                "type": "UPI_QR"
                            }
                        ]
                    }
                }
            }
            
            # Add callback URL if provided
            if callback_url:
                payload["paymentFlow"]["merchantUrls"]["callbackUrl"] = callback_url
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'O-Bearer {auth_token}',
            }
            
            response = requests.post(self.payment_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                payment_data = response.json()
                
                # Try to create payment transaction record if we have order and user
                try:
                    from django.contrib.auth import get_user_model
                    from orders.models import Order
                    
                    User = get_user_model()
                    order = Order.objects.get(order_number=order_id)
                    user = User.objects.get(id=user_id)
                    
                    transaction = PaymentTransaction.objects.create(
                        gateway=self.gateway,
                        order=order,
                        user=user,
                        gateway_transaction_id=payment_data.get('orderId', ''),
                        amount=Decimal(str(amount)),
                        currency='INR',
                        status='pending',
                        gateway_response=payment_data
                    )
                    
                    return {
                        'success': True,
                        'payment_url': payment_data.get('redirectUrl'),
                        'transaction_id': transaction.id,
                        'gateway_order_id': payment_data.get('orderId')
                    }
                    
                except Exception as create_error:
                    # If transaction creation fails, still return success with payment URL
                    return {
                        'success': True,
                        'payment_url': payment_data.get('redirectUrl'),
                        'transaction_id': None,
                        'gateway_order_id': payment_data.get('orderId')
                    }
                
            else:
                error_data = response.json() if response.content else {'message': 'Unknown error'}
                return {
                    'success': False,
                    'error': error_data.get('message', f'HTTP {response.status_code}'),
                    'details': error_data
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Payment creation failed: {str(e)}'
            }
    
    def check_payment_status(self, merchant_order_id):
        """Check payment status"""
        try:
            auth_token = self.get_auth_token()
            if not auth_token:
                return {
                    'success': False,
                    'error': 'Authentication failed'
                }
            
            url = f"{self.status_url}/{merchant_order_id}/status"
            headers = {
                'Authorization': f'O-Bearer {auth_token}',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                status_data = response.json()
                return {
                    'success': True,
                    'data': status_data
                }
            else:
                return {
                    'success': False,
                    'error': f'Status check failed: HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Status check error: {str(e)}'
            }
    
    def process_webhook(self, webhook_data):
        """Process webhook from PhonePe"""
        try:
            # Extract transaction details
            merchant_order_id = webhook_data.get('merchantOrderId')
            payment_status = webhook_data.get('state', '').upper()
            
            if not merchant_order_id:
                return {'success': False, 'error': 'Missing merchant order ID'}
            
            # Find transaction
            try:
                transaction = PaymentTransaction.objects.get(
                    merchant_transaction_id=merchant_order_id
                )
            except PaymentTransaction.DoesNotExist:
                return {'success': False, 'error': 'Transaction not found'}
            
            # Update transaction status
            status_mapping = {
                'SUCCESS': 'SUCCESS',
                'FAILED': 'FAILED',
                'PENDING': 'PENDING',
                'CANCELLED': 'CANCELLED'
            }
            
            transaction.status = status_mapping.get(payment_status, 'FAILED')
            transaction.gateway_response = webhook_data
            transaction.processed_at = timezone.now()
            transaction.save()
            
            return {
                'success': True,
                'status': transaction.status,
                'transaction_id': transaction.id
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Webhook processing failed: {str(e)}'
            }
    
    def initiate_refund(self, transaction_id, amount, reason="Customer request"):
        """Initiate refund - to be implemented when needed"""
        return {
            'success': False,
            'error': 'Refund functionality not implemented yet'
        }
