import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatSession, ChatMessage
import uuid

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'chat_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', 'chat_message')
        
        if message_type == 'chat_message':
            message = text_data_json['message']
            
            # Save message to database
            chat_message = await self.save_message(message)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender': self.scope['user'].username,
                    'timestamp': chat_message.created_at.isoformat(),
                }
            )
        elif message_type == 'typing':
            # Handle typing indicators
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user': self.scope['user'].username,
                    'is_typing': text_data_json.get('is_typing', False)
                }
            )
    
    async def chat_message(self, event):
        message = event['message']
        sender = event['sender']
        timestamp = event['timestamp']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message,
            'sender': sender,
            'timestamp': timestamp
        }))
    
    async def typing_indicator(self, event):
        # Send typing indicator to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': event['user'],
            'is_typing': event['is_typing']
        }))
    
    @database_sync_to_async
    def save_message(self, message):
        try:
            session = ChatSession.objects.get(session_id=self.session_id)
            chat_message = ChatMessage.objects.create(
                session=session,
                sender=self.scope['user'],
                content=message,
                message_type='text'
            )
            return chat_message
        except ChatSession.DoesNotExist:
            return None

class AdminChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Only allow admin users
        if not self.scope['user'].is_staff:
            await self.close()
            return
        
        self.room_group_name = 'admin_chat_monitor'
        
        # Join admin monitoring group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        action = text_data_json.get('action')
        
        if action == 'takeover_session':
            session_id = text_data_json.get('session_id')
            reason = text_data_json.get('reason', '')
            
            # Handle admin takeover
            success = await self.takeover_session(session_id, reason)
            
            await self.send(text_data=json.dumps({
                'type': 'takeover_response',
                'success': success,
                'session_id': session_id
            }))
    
    async def new_chat_session(self, event):
        # Notify admin of new chat sessions
        await self.send(text_data=json.dumps({
            'type': 'new_session',
            'session_data': event['session_data']
        }))
    
    @database_sync_to_async
    def takeover_session(self, session_id, reason):
        try:
            from django.utils import timezone
            session = ChatSession.objects.get(session_id=session_id)
            session.taken_over_by_admin = self.scope['user']
            session.takeover_reason = reason
            session.taken_over_at = timezone.now()
            session.status = 'escalated'
            session.save()
            
            # Create system message
            ChatMessage.objects.create(
                session=session,
                sender=self.scope['user'],
                message_type='system',
                content=f"Chat taken over by admin: {reason}",
                system_event='admin_takeover'
            )
            
            return True
        except ChatSession.DoesNotExist:
            return False
