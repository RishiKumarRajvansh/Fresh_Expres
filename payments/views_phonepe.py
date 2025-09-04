"""
PhonePe Payment Views
Handles PhonePe callbacks, webhooks, and payment processing
"""
import json
import base64
import hashlib
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings
from django.contrib.auth.decorators import login_required
from payments.models_advanced import PaymentTransaction, PaymentGateway
from payments.services_payment import PaymentProcessor

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def phonepe_callback(request):
    """Handle PhonePe payment callback"""
    try:
        # Get response data
        response_data = request.POST.dict()
        logger.info(f"PhonePe callback received: {response_data}")
        
        # Extract transaction ID
        merchant_transaction_id = response_data.get('transactionId')
        if not merchant_transaction_id:
            logger.error("No transaction ID in PhonePe callback")
            return render(request, 'payments/payment_failed.html', {
                'error': 'Invalid payment response'
            })
        
        # Find the transaction
        try:
            # Extract original transaction ID from merchant transaction ID
            if merchant_transaction_id.startswith('MT'):
                original_transaction_id = merchant_transaction_id[2:]  # Remove 'MT' prefix
            else:
                original_transaction_id = merchant_transaction_id
                
            transaction = PaymentTransaction.objects.get(transaction_id=original_transaction_id)
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction not found for ID: {merchant_transaction_id}")
            return render(request, 'payments/payment_failed.html', {
                'error': 'Transaction not found'
            })
        
        # Process payment verification
        processor = PaymentProcessor()
        verification_result = processor.verify_payment(
            transaction_id=str(transaction.transaction_id),
            gateway_response=response_data
        )
        
        if verification_result['success']:
            # Payment successful
            return render(request, 'payments/payment_success.html', {
                'transaction': transaction,
                'amount': verification_result.get('amount')
            })
        else:
            # Payment failed
            return render(request, 'payments/payment_failed.html', {
                'error': verification_result.get('error', 'Payment verification failed'),
                'transaction': transaction
            })
            
    except Exception as e:
        logger.error(f"PhonePe callback error: {str(e)}")
        return render(request, 'payments/payment_failed.html', {
            'error': 'Payment processing error'
        })


@csrf_exempt
@require_POST
def phonepe_webhook(request):
    """Handle PhonePe payment webhook"""
    try:
        # Get webhook data
        webhook_data = json.loads(request.body)
        logger.info(f"PhonePe webhook received: {webhook_data}")
        
        # Verify webhook signature
        phonepe_gateway = PaymentGateway.objects.filter(
            gateway_type='phonepe', 
            is_active=True
        ).first()
        
        if not phonepe_gateway:
            logger.error("PhonePe gateway not configured")
            return HttpResponse(status=400)
        
        # Extract signature from headers
        signature = request.headers.get('X-VERIFY')
        if not signature:
            logger.error("No signature in PhonePe webhook")
            return HttpResponse(status=400)
        
        # Verify signature
        if not verify_phonepe_signature(webhook_data, signature, phonepe_gateway):
            logger.error("Invalid PhonePe webhook signature")
            return HttpResponse(status=400)
        
        # Process webhook
        response_data = webhook_data.get('response', {})
        merchant_transaction_id = response_data.get('merchantTransactionId')
        
        if merchant_transaction_id:
            # Find and update transaction
            try:
                if merchant_transaction_id.startswith('MT'):
                    original_transaction_id = merchant_transaction_id[2:]
                else:
                    original_transaction_id = merchant_transaction_id
                
                transaction = PaymentTransaction.objects.get(transaction_id=original_transaction_id)
                
                # Update transaction status based on webhook data
                state = response_data.get('state')
                if state == 'COMPLETED':
                    transaction.status = 'success'
                    transaction.gateway_response = webhook_data
                    transaction.save()
                    
                    # Use OrderWorkflowService for payment success
                    from orders.services import OrderWorkflowService
                    if transaction.order:
                        OrderWorkflowService.handle_payment_success(
                            order=transaction.order,
                            payment_details=webhook_data
                        )
                    
                    logger.info(f"Payment successful via webhook: {merchant_transaction_id}")
                
                elif state == 'FAILED':
                    transaction.status = 'failed'
                    transaction.gateway_response = webhook_data
                    transaction.save()
                    
                    # Use OrderWorkflowService for payment failure
                    from orders.services import OrderWorkflowService
                    if transaction.order:
                        OrderWorkflowService.handle_payment_failure(
                            order=transaction.order,
                            error_details=webhook_data
                        )
                    
                    logger.warning(f"Payment failed via webhook: {merchant_transaction_id}")
                
            except PaymentTransaction.DoesNotExist:
                logger.error(f"Transaction not found in webhook: {merchant_transaction_id}")
                return HttpResponse(status=404)
                    
                transaction = PaymentTransaction.objects.get(transaction_id=original_transaction_id)
                
                # Update transaction based on webhook data
                payment_state = response_data.get('state')
                if payment_state == 'COMPLETED':
                    if transaction.status != 'success':
                        transaction.mark_success(
                            gateway_transaction_id=response_data.get('transactionId'),
                            gateway_response=response_data
                        )
                        logger.info(f"Transaction {transaction.transaction_id} marked as successful via webhook")
                elif payment_state == 'FAILED':
                    if transaction.status not in ['failed', 'cancelled']:
                        transaction.mark_failed(
                            error_message=response_data.get('responseCodeDescription', 'Payment failed'),
                            gateway_response=response_data
                        )
                        logger.info(f"Transaction {transaction.transaction_id} marked as failed via webhook")
                
            except PaymentTransaction.DoesNotExist:
                logger.error(f"Transaction not found for webhook: {merchant_transaction_id}")
        
        return HttpResponse("OK")
        
    except Exception as e:
        logger.error(f"PhonePe webhook error: {str(e)}")
        return HttpResponse(status=500)


@csrf_exempt
@require_POST
def phonepe_refund_webhook(request):
    """Handle PhonePe refund webhook"""
    try:
        webhook_data = json.loads(request.body)
        logger.info(f"PhonePe refund webhook received: {webhook_data}")
        
        # Process refund webhook
        response_data = webhook_data.get('response', {})
        merchant_refund_id = response_data.get('merchantTransactionId')
        
        if merchant_refund_id:
            try:
                if merchant_refund_id.startswith('RF'):
                    refund_transaction_id = merchant_refund_id[2:]
                else:
                    refund_transaction_id = merchant_refund_id
                    
                refund_transaction = PaymentTransaction.objects.get(transaction_id=refund_transaction_id)
                
                refund_state = response_data.get('state')
                if refund_state == 'COMPLETED':
                    if refund_transaction.status != 'success':
                        refund_transaction.mark_success(
                            gateway_transaction_id=response_data.get('transactionId'),
                            gateway_response=response_data
                        )
                        logger.info(f"Refund {refund_transaction.transaction_id} marked as successful")
                elif refund_state == 'FAILED':
                    if refund_transaction.status != 'failed':
                        refund_transaction.mark_failed(
                            error_message=response_data.get('responseCodeDescription', 'Refund failed'),
                            gateway_response=response_data
                        )
                        logger.info(f"Refund {refund_transaction.transaction_id} marked as failed")
                        
            except PaymentTransaction.DoesNotExist:
                logger.error(f"Refund transaction not found: {merchant_refund_id}")
        
        return HttpResponse("OK")
        
    except Exception as e:
        logger.error(f"PhonePe refund webhook error: {str(e)}")
        return HttpResponse(status=500)


@login_required
@require_http_methods(["POST"])
def initiate_phonepe_payment(request):
    """Initiate PhonePe payment"""
    try:
        # Get order ID from request
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({
                'success': False,
                'error': 'Order ID required'
            })
        
        # Get order
        from orders.models import Order  # Import here to avoid circular imports
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Order not found'
            })
        
        # Get or create PhonePe payment method
        from payments.models_advanced import PaymentMethod
        payment_method, created = PaymentMethod.objects.get_or_create(
            user=request.user,
            payment_type='upi',
            defaults={'is_default': True}
        )
        
        # Initiate payment
        processor = PaymentProcessor()
        result = processor.initiate_payment(
            order=order,
            payment_method=payment_method,
            amount=order.total_amount,
            currency='INR'
        )
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'payment_url': result.get('payment_url'),
                'transaction_id': result.get('transaction_id')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error')
            })
            
    except Exception as e:
        logger.error(f"PhonePe payment initiation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Payment initiation failed'
        })


def verify_phonepe_signature(data: dict, signature: str, gateway: PaymentGateway) -> bool:
    """Verify PhonePe webhook signature"""
    try:
        # Get salt key from gateway config
        config = gateway.get_api_config()
        salt_key = config.get('salt_key')
        salt_index = config.get('salt_index', 1)
        
        if not salt_key:
            logger.error("Salt key not configured for PhonePe gateway")
            return False
        
        # Create signature string
        # Note: Actual signature verification logic depends on PhonePe's specification
        # This is a simplified version
        data_string = json.dumps(data, separators=(',', ':'))
        string_to_hash = f"{data_string}{salt_key}"
        
        expected_signature = hashlib.sha256(string_to_hash.encode()).hexdigest() + "###" + str(salt_index)
        
        return signature == expected_signature
        
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False


def payment_status_check(request, transaction_id):
    """Check payment status"""
    try:
        transaction = PaymentTransaction.objects.get(transaction_id=transaction_id)
        
        # Check if user is authorized to view this transaction
        if request.user != transaction.user:
            return JsonResponse({
                'success': False,
                'error': 'Unauthorized'
            }, status=403)
        
        return JsonResponse({
            'success': True,
            'status': transaction.status,
            'amount': str(transaction.amount),
            'currency': transaction.currency,
            'created_at': transaction.initiated_at.isoformat()
        })
        
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Transaction not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Payment status check error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Status check failed'
        })
