# FAQ Views
from django.views.generic import ListView
from django.http import JsonResponse
from django.utils import timezone
import uuid
import json
from .models import FAQ, FAQCategory, ChatConversation, ChatMessage, BotResponse
from .chatbot_ai import get_ai_response

class FAQListView(ListView):
    model = FAQCategory
    template_name = 'core/faq.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return FAQCategory.objects.filter(is_active=True).prefetch_related('faqs')

# Chat Support Views
def get_session_id(request):
    """Get or create session ID for chat"""
    session_id = request.session.get('chat_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['chat_session_id'] = session_id
    return session_id

def chat_start(request):
    """Start a chat conversation"""
    if request.method == 'POST':
        session_id = get_session_id(request)
        
        # Get or create conversation
        conversation, created = ChatConversation.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': request.user if request.user.is_authenticated else None,
                'is_active': True,
                'is_bot_handled': True
            }
        )
        
        # Get user message
        message = request.POST.get('message', '').strip()
        if message:
            # Save user message
            ChatMessage.objects.create(
                conversation=conversation,
                sender_type='user',
                sender_name=request.user.username if request.user.is_authenticated else 'Guest',
                message=message
            )
            
            # Get bot response
            bot_response = get_bot_response(message, conversation)
            
            return JsonResponse({
                'success': True,
                'response': bot_response,
                'session_id': session_id
            })
    
    return JsonResponse({'success': False})

def get_bot_response(message, conversation):
    """Get AI-powered bot response using enhanced chatbot"""
    try:
        # Get AI response
        ai_response, should_escalate = get_ai_response(message, conversation)
        
        # Save bot response
        ChatMessage.objects.create(
            conversation=conversation,
            sender_type='bot',
            sender_name='FreshBot',
            message=ai_response
        )
        
        # Handle escalation
        if should_escalate:
            conversation.assigned_to_agent = True
            conversation.is_bot_handled = False
            conversation.save()
            
            # Add escalation message
            escalation_msg = "I'm connecting you with our expert support team for personalized assistance. Please wait a moment."
            ChatMessage.objects.create(
                conversation=conversation,
                sender_type='bot',
                sender_name='FreshBot',
                message=escalation_msg
            )
        
        return ai_response
        
    except Exception as e:
        # Fallback to original logic if AI fails
        return get_fallback_response(message, conversation)

def get_fallback_response(message, conversation):
    """Fallback response system using original bot responses"""
    message_lower = message.lower()
    
    # Try to find matching bot response
    bot_responses = BotResponse.objects.filter(is_active=True).order_by('-priority')
    
    for bot_response in bot_responses:
        keywords = bot_response.get_keywords_list()
        if any(keyword in message_lower for keyword in keywords):
            # Save bot response
            ChatMessage.objects.create(
                conversation=conversation,
                sender_type='bot',
                sender_name='FreshBot',
                message=bot_response.response
            )
            
            # Check if should escalate to agent
            if bot_response.escalate_to_agent:
                conversation.assigned_to_agent = True
                conversation.is_bot_handled = False
                conversation.save()
                
                # Add escalation message
                ChatMessage.objects.create(
                    conversation=conversation,
                    sender_type='bot',
                    sender_name='FreshBot',
                    message="I'm connecting you with our support agent. Please wait a moment."
                )
            
            return bot_response.response
    
    # Default response if no match found
    default_response = "I understand you need help. Let me connect you with our support team for better assistance."
    
    ChatMessage.objects.create(
        conversation=conversation,
        sender_type='bot',
        sender_name='FreshBot',
        message=default_response
    )
    
    # Escalate to agent for unknown queries
    conversation.assigned_to_agent = True
    conversation.is_bot_handled = False
    conversation.save()
    
    return default_response

def chat_messages(request):
    """Get chat messages for a conversation"""
    session_id = request.session.get('chat_session_id')
    if not session_id:
        return JsonResponse({'messages': []})
    
    try:
        conversation = ChatConversation.objects.get(session_id=session_id)
        messages = conversation.messages.all().order_by('timestamp')
        
        message_data = []
        for msg in messages:
            message_data.append({
                'sender_type': msg.sender_type,
                'sender_name': msg.sender_name,
                'message': msg.message,
                'timestamp': msg.timestamp.isoformat()
            })
        
        return JsonResponse({
            'messages': message_data,
            'is_agent_assigned': conversation.assigned_to_agent
        })
    except ChatConversation.DoesNotExist:
        return JsonResponse({'messages': []})

def chat_close(request):
    """Close chat conversation"""
    session_id = request.session.get('chat_session_id')
    if session_id:
        try:
            conversation = ChatConversation.objects.get(session_id=session_id)
            conversation.is_active = False
            conversation.save()
            
            # Clear session
            if 'chat_session_id' in request.session:
                del request.session['chat_session_id']
            
            return JsonResponse({'success': True})
        except ChatConversation.DoesNotExist:
            pass
    
    return JsonResponse({'success': False})
