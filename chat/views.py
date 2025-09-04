from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.utils import timezone
from .models import ChatSession, ChatMessage
from orders.models import Order
from stores.models import Store

class ChatListView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/chat_interface.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if this is order-specific support
        order_id = self.request.GET.get('order_id')
        order_number = self.request.GET.get('order_number')
        store_id = self.request.GET.get('store_id')
        
        if order_id and order_number:
            try:
                order = Order.objects.select_related('store').get(
                    order_id=order_id,
                    user=self.request.user
                )
                
                # Find or create chat session for this order
                chat_session, created = ChatSession.objects.get_or_create(
                    customer=self.request.user,
                    store=order.store,
                    order=order,
                    session_type='order_support',
                    status='active',
                    defaults={
                        'subject': f'Support for Order #{order_number}'
                    }
                )
                
                context['chat_session'] = chat_session
                context['order'] = order
                context['is_order_support'] = True
                
                # Add initial system message if newly created
                if created:
                    ChatMessage.objects.create(
                        session=chat_session,
                        sender=None,  # System message
                        message_type='system',
                        content=f"Support chat initiated for Order #{order_number}. A store representative will assist you shortly."
                    )
                
            except Order.DoesNotExist:
                return redirect('orders:order_list')
        
        else:
            # General support - find or create general chat session
            chat_session, created = ChatSession.objects.get_or_create(
                customer=self.request.user,
                store=None,  # General support
                order=None,
                session_type='general_inquiry',
                status='active',
                defaults={
                    'subject': 'General Support Inquiry'
                }
            )
            
            context['chat_session'] = chat_session
            context['is_order_support'] = False
            
        # Get recent messages for this session
        if 'chat_session' in context:
            messages = ChatMessage.objects.filter(
                session=context['chat_session']
            ).select_related('sender').order_by('created_at')
            context['messages'] = messages
        
        return context

class StartChatView(LoginRequiredMixin, FormView):
    template_name = 'chat/start_chat.html'

class ChatSessionView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/chat_session.html'

class CloseChatView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class RateChatView(LoginRequiredMixin, FormView):
    template_name = 'chat/rate_chat.html'

class StoreChatDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/store_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if user has access to store chat (store_owner or store_staff)
        if not hasattr(self.request.user, 'user_type') or self.request.user.user_type not in ['store_owner', 'store_staff']:
            return redirect('core:home')
        
        # Get store for this user
        try:
            if self.request.user.user_type == 'store_owner':
                store = Store.objects.get(owner=self.request.user)
            else:  # store_staff
                store = Store.objects.get(staff=self.request.user)  # This might need adjustment based on your store staff model
                
            # Get active chat sessions for this store
            active_chats = ChatSession.objects.filter(
                store=store,
                status='active'
            ).select_related('customer', 'order').order_by('-updated_at')
            
            # Get order-specific support chats
            order_support_chats = active_chats.filter(session_type='order_support')
            general_chats = active_chats.filter(session_type='general_inquiry')
            
            context.update({
                'store': store,
                'active_chats': active_chats,
                'order_support_chats': order_support_chats,
                'general_chats': general_chats,
                'total_active': active_chats.count(),
            })
            
        except Store.DoesNotExist:
            return redirect('core:home')
        
        return context

class StoreChatSessionView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/store_session.html'

class ChatTemplatesView(LoginRequiredMixin, ListView):
    template_name = 'chat/templates.html'
    context_object_name = 'templates'
    
    def get_queryset(self):
        return []

class AutoResponsesView(LoginRequiredMixin, ListView):
    template_name = 'chat/auto_responses.html'
    context_object_name = 'responses'
    
    def get_queryset(self):
        return []

class AdminChatDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/admin_dashboard.html'

class AdminChatSessionView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/admin_session.html'

class TakeoverChatView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class ChatAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/analytics.html'

class MessageAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'messages': []})
    
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class SessionMessagesAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'messages': []})

class NotificationsAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'notifications': []})

class MarkMessagesReadAPIView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class UploadImageView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True, 'url': '/media/default.jpg'})

class UploadFileView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True, 'url': '/media/default.pdf'})


@method_decorator(login_required, name='dispatch')
class StoreChatSessionView(View):
    """Individual chat session view for store managers"""
    
    def get(self, request, session_id):
        # Get the chat session
        try:
            chat_session = ChatSession.objects.select_related(
                'customer', 'store', 'order'
            ).get(session_id=session_id)
        except ChatSession.DoesNotExist:
            return redirect('chat:store_dashboard')
        
        # Check if user has access to this store
        if not (request.user.is_staff or request.user.is_superuser):
            # Check if user is associated with this store
            if not hasattr(request.user, 'user_type') or request.user.user_type not in ['store_owner', 'store_staff']:
                return redirect('core:login')
            
            # Get user's store
            try:
                if request.user.user_type == 'store_owner':
                    user_store = Store.objects.get(owner=request.user)
                else:
                    user_store = Store.objects.get(staff=request.user)
                
                if user_store != chat_session.store:
                    return redirect('chat:store_dashboard')
            except Store.DoesNotExist:
                return redirect('core:login')
        
        # Get chat messages
        messages_list = chat_session.messages.order_by('timestamp')
        
        context = {
            'chat_session': chat_session,
            'messages': messages_list,
            'store': chat_session.store,
            'customer': chat_session.customer,
            'order': chat_session.order if chat_session.session_type == 'order_support' else None,
        }
        
        return render(request, 'chat/store_chat_session.html', context)
    
    def post(self, request, session_id):
        # Handle sending messages
        try:
            chat_session = ChatSession.objects.get(session_id=session_id)
        except ChatSession.DoesNotExist:
            return JsonResponse({'error': 'Chat session not found'}, status=404)
        
        # Check access permissions
        if not (request.user.is_staff or request.user.is_superuser):
            if not hasattr(request.user, 'user_type') or request.user.user_type not in ['store_owner', 'store_staff']:
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            try:
                if request.user.user_type == 'store_owner':
                    user_store = Store.objects.get(owner=request.user)
                else:
                    user_store = Store.objects.get(staff=request.user)
                
                if user_store != chat_session.store:
                    return JsonResponse({'error': 'Access denied'}, status=403)
            except Store.DoesNotExist:
                return JsonResponse({'error': 'Access denied'}, status=403)
        
        message_text = request.POST.get('message', '').strip()
        if not message_text:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Create the message
        chat_message = chat_session.messages.create(
            sender=request.user,
            message=message_text
        )
        
        # Update chat session
        chat_session.updated_at = timezone.now()
        chat_session.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': chat_message.id,
                'message': chat_message.message,
                'sender_name': chat_message.sender.get_full_name() or chat_message.sender.username,
                'timestamp': chat_message.timestamp.strftime('%H:%M'),
                'is_staff': chat_message.sender.is_staff or hasattr(chat_message.sender, 'user_type')
            }
        })
