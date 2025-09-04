"""
Real-time WebSocket Consumers for Live Updates
Handles stock updates, order tracking, and delivery tracking
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


class StockUpdateConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time stock updates"""
    
    async def connect(self):
        self.store_id = self.scope['url_route']['kwargs'].get('store_id')
        self.product_id = self.scope['url_route']['kwargs'].get('product_id')
        
        # Join group based on store or product
        if self.store_id:
            self.group_name = f'stock_store_{self.store_id}'
        elif self.product_id:
            self.group_name = f'stock_product_{self.product_id}'
        else:
            self.group_name = 'stock_global'
        
        # Join stock updates group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"StockUpdate WebSocket connected: {self.group_name}")
    
    async def disconnect(self, close_code):
        # Leave stock updates group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"StockUpdate WebSocket disconnected: {self.group_name}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_product':
                # Subscribe to specific product updates
                product_id = data.get('product_id')
                if product_id:
                    product_group = f'stock_product_{product_id}'
                    await self.channel_layer.group_add(product_group, self.channel_name)
                    await self.send(text_data=json.dumps({
                        'type': 'subscription_confirmed',
                        'product_id': product_id
                    }))
            
            elif message_type == 'unsubscribe_product':
                # Unsubscribe from product updates
                product_id = data.get('product_id')
                if product_id:
                    product_group = f'stock_product_{product_id}'
                    await self.channel_layer.group_discard(product_group, self.channel_name)
                    await self.send(text_data=json.dumps({
                        'type': 'unsubscription_confirmed',
                        'product_id': product_id
                    }))
            
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    async def stock_update(self, event):
        """Send stock update to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'stock_update',
            'product_id': event['product_id'],
            'store_id': event['store_id'],
            'stock_quantity': event['stock_quantity'],
            'is_available': event['is_available'],
            'price': event.get('price'),
            'timestamp': event['timestamp']
        }))
    
    async def low_stock_alert(self, event):
        """Send low stock alert to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'low_stock_alert',
            'product_id': event['product_id'],
            'store_id': event['store_id'],
            'current_stock': event['current_stock'],
            'threshold': event['threshold'],
            'message': event['message']
        }))


class OrderTrackingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time order tracking"""
    
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.group_name = f'order_{self.order_id}'
        
        # Check if user is authorized to track this order
        user = self.scope.get('user')
        if user and user.is_authenticated:
            is_authorized = await self.check_order_authorization(user, self.order_id)
            if is_authorized:
                # Join order tracking group
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()
                
                # Send current order status
                await self.send_current_order_status()
                logger.info(f"OrderTracking WebSocket connected: order {self.order_id}")
            else:
                await self.close(code=4403)  # Forbidden
        else:
            await self.close(code=4401)  # Unauthorized
    
    async def disconnect(self, close_code):
        # Leave order tracking group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"OrderTracking WebSocket disconnected: order {self.order_id}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'request_update':
                # Client requesting current status
                await self.send_current_order_status()
            
            elif message_type == 'ping':
                # Keep-alive ping
                await self.send(text_data=json.dumps({'type': 'pong'}))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    @database_sync_to_async
    def check_order_authorization(self, user, order_id):
        """Check if user is authorized to track this order"""
        from orders.models import Order
        try:
            order = Order.objects.get(id=order_id)
            # User owns the order or is admin/staff
            return order.user == user or user.is_staff
        except Order.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_order_status(self):
        """Get current order status and details"""
        from orders.models import Order
        try:
            order = Order.objects.select_related(
                'store', 'delivery_assignment__delivery_agent__user'
            ).get(id=self.order_id)
            
            status_data = {
                'order_id': order.id,
                'status': order.status,
                'estimated_delivery': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
                'store_name': order.store.name,
                'total_amount': str(order.total_amount),
                'created_at': order.created_at.isoformat(),
            }
            
            # Add delivery agent info if assigned
            if hasattr(order, 'delivery_assignment') and order.delivery_assignment:
                assignment = order.delivery_assignment
                status_data.update({
                    'delivery_agent': {
                        'name': assignment.delivery_agent.user.get_full_name(),
                        'phone': assignment.delivery_agent.phone,
                        'current_location': assignment.current_location,
                        'estimated_arrival': assignment.estimated_arrival_time.isoformat() if assignment.estimated_arrival_time else None,
                    }
                })
            
            return status_data
        except Order.DoesNotExist:
            return None
    
    async def send_current_order_status(self):
        """Send current order status to client"""
        status_data = await self.get_order_status()
        if status_data:
            await self.send(text_data=json.dumps({
                'type': 'order_status',
                **status_data
            }))
    
    async def order_status_update(self, event):
        """Send order status update to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'order_status_update',
            'order_id': event['order_id'],
            'status': event['status'],
            'message': event.get('message', ''),
            'estimated_delivery': event.get('estimated_delivery'),
            'timestamp': event['timestamp']
        }))
    
    async def delivery_location_update(self, event):
        """Send delivery agent location update"""
        await self.send(text_data=json.dumps({
            'type': 'delivery_location_update',
            'order_id': event['order_id'],
            'agent_location': event['agent_location'],
            'estimated_arrival': event.get('estimated_arrival'),
            'distance_remaining': event.get('distance_remaining'),
            'timestamp': event['timestamp']
        }))


class DeliveryTrackingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time delivery tracking"""
    
    async def connect(self):
        self.delivery_id = self.scope['url_route']['kwargs']['delivery_id']
        self.group_name = f'delivery_{self.delivery_id}'
        
        # Check authorization
        user = self.scope.get('user')
        if user and user.is_authenticated:
            is_authorized = await self.check_delivery_authorization(user, self.delivery_id)
            if is_authorized:
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()
                
                # Send current delivery status
                await self.send_current_delivery_status()
                logger.info(f"DeliveryTracking WebSocket connected: delivery {self.delivery_id}")
            else:
                await self.close(code=4403)
        else:
            await self.close(code=4401)
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"DeliveryTracking WebSocket disconnected: delivery {self.delivery_id}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'request_location':
                await self.send_current_delivery_status()
            
            elif message_type == 'update_location' and await self.is_delivery_agent():
                # Delivery agent updating their location
                location_data = data.get('location', {})
                await self.update_agent_location(location_data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    @database_sync_to_async
    def check_delivery_authorization(self, user, delivery_id):
        """Check if user can track this delivery"""
        from delivery.models import DeliveryAssignment
        try:
            delivery = DeliveryAssignment.objects.select_related(
                'order__user', 'delivery_agent__user'
            ).get(id=delivery_id)
            
            # Customer, delivery agent, or admin
            return (delivery.order.user == user or 
                   delivery.delivery_agent.user == user or 
                   user.is_staff)
        except DeliveryAssignment.DoesNotExist:
            return False
    
    @database_sync_to_async
    def is_delivery_agent(self):
        """Check if current user is the delivery agent for this delivery"""
        from delivery.models import DeliveryAssignment
        user = self.scope.get('user')
        try:
            delivery = DeliveryAssignment.objects.get(id=self.delivery_id)
            return delivery.delivery_agent.user == user
        except DeliveryAssignment.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_delivery_status(self):
        """Get current delivery status and location"""
        from delivery.models import DeliveryAssignment
        try:
            delivery = DeliveryAssignment.objects.select_related(
                'order', 'delivery_agent__user'
            ).get(id=self.delivery_id)
            
            return {
                'delivery_id': delivery.id,
                'order_id': delivery.order.id,
                'status': delivery.status,
                'agent_name': delivery.delivery_agent.user.get_full_name(),
                'agent_phone': delivery.delivery_agent.phone,
                'current_location': delivery.current_location,
                'pickup_time': delivery.pickup_time.isoformat() if delivery.pickup_time else None,
                'estimated_arrival': delivery.estimated_arrival_time.isoformat() if delivery.estimated_arrival_time else None,
                'delivery_notes': delivery.delivery_notes
            }
        except DeliveryAssignment.DoesNotExist:
            return None
    
    async def send_current_delivery_status(self):
        """Send current delivery status to client"""
        status_data = await self.get_delivery_status()
        if status_data:
            await self.send(text_data=json.dumps({
                'type': 'delivery_status',
                **status_data
            }))
    
    @database_sync_to_async
    def update_agent_location(self, location_data):
        """Update delivery agent's current location"""
        from delivery.models import DeliveryAssignment, DeliveryTracking
        try:
            delivery = DeliveryAssignment.objects.get(id=self.delivery_id)
            
            # Update current location
            delivery.current_location = location_data
            delivery.save()
            
            # Create tracking record
            DeliveryTracking.objects.create(
                delivery_assignment=delivery,
                latitude=location_data.get('latitude'),
                longitude=location_data.get('longitude'),
                accuracy=location_data.get('accuracy'),
                timestamp=timezone.now()
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to update agent location: {str(e)}")
            return False
    
    async def delivery_status_update(self, event):
        """Send delivery status update to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'delivery_status_update',
            'delivery_id': event['delivery_id'],
            'status': event['status'],
            'message': event.get('message', ''),
            'timestamp': event['timestamp']
        }))
    
    async def agent_location_update(self, event):
        """Send agent location update to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'agent_location_update',
            'delivery_id': event['delivery_id'],
            'location': event['location'],
            'estimated_arrival': event.get('estimated_arrival'),
            'distance_remaining': event.get('distance_remaining'),
            'timestamp': event['timestamp']
        }))


class ChatConsumer(AsyncWebsocketConsumer):
    """Enhanced WebSocket consumer for customer support chat"""
    
    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return
        
        self.room_id = self.scope['url_route']['kwargs'].get('room_id')
        
        if not self.room_id:
            # Create or get user's support room
            self.room_id = await self.get_or_create_support_room()
        
        self.room_group_name = f'chat_{self.room_id}'
        
        # Join chat group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send recent chat history
        await self.send_chat_history()
        
        # Mark user as online
        await self.mark_user_online()
        
        logger.info(f"Chat WebSocket connected: user {self.user.id}, room {self.room_id}")
    
    async def disconnect(self, close_code):
        # Leave chat group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Mark user as offline
        await self.mark_user_offline()
        
        logger.info(f"Chat WebSocket disconnected: user {self.user.id}, room {self.room_id}")
    
    async def receive(self, text_data):
        """Handle chat messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                message = data.get('message', '').strip()
                if message:
                    # Save message to database
                    chat_message = await self.save_chat_message(message)
                    
                    if chat_message:
                        # Broadcast message to room
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'chat_message',
                                'message_id': chat_message.id,
                                'message': message,
                                'user': self.user.username,
                                'user_id': self.user.id,
                                'timestamp': chat_message.created_at.isoformat(),
                                'is_staff': self.user.is_staff
                            }
                        )
            
            elif message_type == 'typing':
                # Broadcast typing indicator
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_typing',
                        'user': self.user.username,
                        'user_id': self.user.id,
                        'is_typing': data.get('is_typing', False)
                    }
                )
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    @database_sync_to_async
    def get_or_create_support_room(self):
        """Get or create support chat room for user"""
        from chat.models import ChatRoom
        room, created = ChatRoom.objects.get_or_create(
            customer=self.user,
            defaults={
                'room_name': f'Support for {self.user.username}',
                'is_active': True
            }
        )
        return room.id
    
    @database_sync_to_async
    def save_chat_message(self, message):
        """Save chat message to database"""
        from chat.models import ChatMessage, ChatRoom
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            chat_message = ChatMessage.objects.create(
                room=room,
                sender=self.user,
                message=message
            )
            return chat_message
        except ChatRoom.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_chat_history(self, limit=50):
        """Get recent chat history"""
        from chat.models import ChatMessage
        messages = ChatMessage.objects.filter(
            room_id=self.room_id
        ).select_related('sender').order_by('-created_at')[:limit]
        
        return [{
            'id': msg.id,
            'message': msg.message,
            'user': msg.sender.username,
            'user_id': msg.sender.id,
            'timestamp': msg.created_at.isoformat(),
            'is_staff': msg.sender.is_staff
        } for msg in reversed(messages)]
    
    async def send_chat_history(self):
        """Send recent chat history to client"""
        history = await self.get_chat_history()
        await self.send(text_data=json.dumps({
            'type': 'chat_history',
            'messages': history
        }))
    
    async def mark_user_online(self):
        """Mark user as online in cache"""
        cache.set(f'user_online_{self.user.id}', True, timeout=300)
    
    async def mark_user_offline(self):
        """Mark user as offline in cache"""
        cache.delete(f'user_online_{self.user.id}')
    
    async def chat_message(self, event):
        """Send chat message to WebSocket client"""
        # Don't echo back to sender
        if event.get('user_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'chat_message',
                'message_id': event['message_id'],
                'message': event['message'],
                'user': event['user'],
                'timestamp': event['timestamp'],
                'is_staff': event['is_staff']
            }))
    
    async def user_typing(self, event):
        """Send typing indicator to WebSocket client"""
        # Don't echo back to sender
        if event.get('user_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'user_typing',
                'user': event['user'],
                'is_typing': event['is_typing']
            }))
    
    async def staff_joined(self, event):
        """Notify when staff member joins chat"""
        await self.send(text_data=json.dumps({
            'type': 'staff_joined',
            'staff_name': event['staff_name'],
            'message': f"{event['staff_name']} has joined the chat"
        }))


# Utility functions for sending real-time updates
async def send_stock_update(product_id, store_id, stock_quantity, is_available, price=None):
    """Send stock update to all connected clients"""
    from channels.layers import get_channel_layer
    from django.utils import timezone
    
    channel_layer = get_channel_layer()
    
    update_data = {
        'type': 'stock_update',
        'product_id': product_id,
        'store_id': store_id,
        'stock_quantity': stock_quantity,
        'is_available': is_available,
        'timestamp': timezone.now().isoformat()
    }
    
    if price is not None:
        update_data['price'] = str(price)
    
    # Send to store-specific group
    await channel_layer.group_send(f'stock_store_{store_id}', update_data)
    
    # Send to product-specific group
    await channel_layer.group_send(f'stock_product_{product_id}', update_data)
    
    # Send to global stock group
    await channel_layer.group_send('stock_global', update_data)


async def send_order_update(order_id, status, message=None, estimated_delivery=None):
    """Send order status update to connected clients"""
    from channels.layers import get_channel_layer
    from django.utils import timezone
    
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(f'order_{order_id}', {
        'type': 'order_status_update',
        'order_id': order_id,
        'status': status,
        'message': message,
        'estimated_delivery': estimated_delivery,
        'timestamp': timezone.now().isoformat()
    })


async def send_delivery_update(delivery_id, status, location=None, estimated_arrival=None):
    """Send delivery status update to connected clients"""
    from channels.layers import get_channel_layer
    from django.utils import timezone
    
    channel_layer = get_channel_layer()
    
    update_data = {
        'type': 'delivery_status_update',
        'delivery_id': delivery_id,
        'status': status,
        'timestamp': timezone.now().isoformat()
    }
    
    if location:
        update_data['location'] = location
    
    if estimated_arrival:
        update_data['estimated_arrival'] = estimated_arrival
    
    await channel_layer.group_send(f'delivery_{delivery_id}', update_data)
