    # Enhanced AI Chatbot for Fresh Express Platform
import re
import json
import datetime
from django.conf import settings
from django.utils import timezone
from typing import Dict, List, Tuple, Optional
from .models import BotResponse, FAQ, ChatConversation, ChatMessage
from catalog.models import Product, Category
from orders.models import Order
from accounts.models import User
from stores.models import Store


class EnhancedChatbot:
    """
    Enhanced AI-powered chatbot with natural language processing
    and comprehensive response capabilities for the Fresh Express platform
    """
    
    def __init__(self):
        self.conversation_context = {}
        self.user_intents = {
            'greeting': ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening'],
            'product_inquiry': ['product', 'item', 'meat', 'seafood', 'chicken', 'fish', 'beef', 'pork', 'lamb'],
            'order_status': ['order', 'status', 'delivery', 'track', 'tracking'],
            'pricing': ['price', 'cost', 'expensive', 'cheap', 'discount', 'offer'],
            'availability': ['available', 'stock', 'out of stock', 'in stock'],
            'delivery': ['delivery', 'shipping', 'deliver', 'when will'],
            'payment': ['payment', 'pay', 'card', 'cash', 'refund'],
            'account': ['account', 'profile', 'login', 'register', 'password'],
            'complaint': ['problem', 'issue', 'complaint', 'wrong', 'bad', 'defective'],
            'compliment': ['good', 'excellent', 'great', 'awesome', 'thank you', 'thanks'],
            'store_location': ['store', 'location', 'address', 'near me', 'branch'],
            'nutrition': ['nutrition', 'healthy', 'calories', 'protein', 'fat'],
            'recipe': ['recipe', 'cook', 'cooking', 'how to prepare', 'marinate'],
            'goodbye': ['bye', 'goodbye', 'see you', 'exit', 'quit']
        }
        
        self.responses = {
            'greeting': [
                "Hello! Welcome to Fresh Express! 🍖🐟 How can I help you today?",
                "Hi there! I'm FreshBot, your personal assistant for all meat and seafood needs. What can I do for you?",
                "Good day! Ready to explore our premium meat and seafood collection? How may I assist you?"
            ],
            'product_inquiry': [
                "I'd be happy to help you find the perfect product! What specific meat or seafood are you looking for?",
                "Great choice! Our platform offers premium quality meat and seafood. Which category interests you most?",
                "Looking for something delicious? Tell me more about what you need - fresh cuts, seafood, or something specific?"
            ],
            'order_status': [
                "I can help you track your order! Could you please provide your order number or the email used for the order?",
                "Let me check your order status. Do you have your order ID handy?",
                "I'll help you track your delivery! What's your order number?"
            ],
            'pricing': [
                "Our prices are competitive and reflect the premium quality of our products. Which items are you interested in?",
                "We offer great value for fresh, quality meat and seafood. What specific products would you like pricing information for?",
                "Looking for the best deals? Check out our daily specials and bulk discounts!"
            ],
            'availability': [
                "Let me check what's available for you! What specific products are you looking for?",
                "I can help you find available items. Which meat or seafood products interest you?",
                "Our inventory updates regularly. What items would you like me to check for availability?"
            ],
            'delivery': [
                "We offer fast, reliable delivery to keep your products fresh! Delivery times vary by location - typically 2-4 hours for express delivery.",
                "Our delivery service ensures your meat and seafood arrive fresh and safe. What area are you ordering to?",
                "We prioritize freshness with our cold-chain delivery system. Where would you like your order delivered?"
            ],
            'payment': [
                "We accept multiple payment methods including cards, digital wallets, and cash on delivery. Need help with payment?",
                "Having payment issues? I can guide you through our secure payment process.",
                "Our payment system is secure and supports various options. What payment method would you prefer?"
            ],
            'account': [
                "Need help with your account? I can guide you through registration, login, or profile updates.",
                "Account assistance is here! Are you looking to create a new account or having trouble accessing your existing one?",
                "I'm here to help with account-related questions. What specific issue are you facing?"
            ],
            'complaint': [
                "I'm sorry to hear about the issue. Your satisfaction is our priority. Can you please describe the problem so I can help resolve it?",
                "That's not the experience we want for you. Let me help make this right. What specific issue occurred?",
                "I apologize for any inconvenience. Please share the details, and I'll ensure we address your concern properly."
            ],
            'compliment': [
                "Thank you so much! We're delighted you're happy with our service. Is there anything else I can help you with?",
                "Your kind words make our day! We're committed to providing the best meat and seafood experience.",
                "We appreciate your feedback! It motivates us to continue delivering excellent service."
            ],
            'store_location': [
                "I can help you find our nearest store location! What area are you in?",
                "We have multiple store locations for your convenience. Which city or area should I search?",
                "Looking for a nearby store? Tell me your location and I'll find the closest branch."
            ],
            'nutrition': [
                "Great question! Our products are rich in protein and essential nutrients. Which specific nutritional information do you need?",
                "Nutrition is important! I can provide details about protein content, calories, and health benefits of our products.",
                "Our meat and seafood are excellent sources of protein, vitamins, and minerals. What nutritional info interests you?"
            ],
            'recipe': [
                "Love to cook? I can suggest some delicious recipes! What type of meat or seafood would you like recipe ideas for?",
                "Cooking tips coming up! Which product do you want to prepare, and what's your preferred cooking style?",
                "Great idea! Fresh ingredients make the best meals. What would you like to cook today?"
            ],
            'goodbye': [
                "Thank you for choosing Fresh Express! Have a wonderful day! 🍖🐟",
                "Goodbye! Come back anytime for premium quality meat and seafood. Take care!",
                "It was great helping you today! See you soon for more fresh deliciousness!"
            ],
            'fallback': [
                "I understand you need assistance. Let me connect you with our specialized support team for detailed help.",
                "That's a great question! While I'm learning, our expert team can provide you with comprehensive assistance.",
                "I want to make sure you get the best help possible. Let me connect you with our support specialists."
            ]
        }
        
    def detect_intent(self, message: str) -> str:
        """Detect user intent from message using keyword matching and context"""
        message_lower = message.lower()
        intent_scores = {}
        
        # Calculate intent scores based on keyword presence
        for intent, keywords in self.user_intents.items():
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
                # Boost score for exact matches
                if keyword == message_lower.strip():
                    score += 2
            intent_scores[intent] = score
        
        # Return intent with highest score, or 'fallback' if no clear intent
        if intent_scores and max(intent_scores.values()) > 0:
            return max(intent_scores.keys(), key=lambda k: intent_scores[k])
        return 'fallback'
    
    def extract_entities(self, message: str) -> Dict[str, List[str]]:
        """Extract entities like product names, numbers, etc. from message"""
        entities = {
            'products': [],
            'numbers': [],
            'locations': [],
            'emails': []
        }
        
        # Extract product-related terms
        product_terms = ['chicken', 'beef', 'pork', 'lamb', 'fish', 'salmon', 'tuna', 'prawns', 'crab', 'lobster']
        for term in product_terms:
            if term in message.lower():
                entities['products'].append(term)
        
        # Extract numbers (could be order IDs, quantities, etc.)
        numbers = re.findall(r'\b\d+\b', message)
        entities['numbers'] = numbers
        
        # Extract email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
        entities['emails'] = emails
        
        return entities
    
    def get_contextual_response(self, message: str, conversation: ChatConversation) -> str:
        """Generate contextual response based on intent and entities"""
        intent = self.detect_intent(message)
        entities = self.extract_entities(message)
        
        # Handle specific scenarios with contextual responses
        if intent == 'product_inquiry' and entities['products']:
            return self.handle_product_inquiry(entities['products'])
        
        elif intent == 'order_status' and entities['numbers']:
            return self.handle_order_status_inquiry(entities['numbers'], conversation)
        
        elif intent == 'pricing' and entities['products']:
            return self.handle_pricing_inquiry(entities['products'])
        
        elif intent == 'availability' and entities['products']:
            return self.handle_availability_inquiry(entities['products'])
        
        elif intent == 'store_location':
            return self.handle_store_location_inquiry(message)
        
        elif intent == 'complaint':
            return self.handle_complaint(message)
        
        # Return random response from intent category
        import random
        responses = self.responses.get(intent, self.responses['fallback'])
        return random.choice(responses)
    
    def handle_product_inquiry(self, products: List[str]) -> str:
        """Handle specific product inquiries"""
        try:
            # Try to find actual products in database
            found_products = []
            for product_name in products:
                # Search for products containing the keyword
                matching_products = Product.objects.filter(
                    name__icontains=product_name,
                    is_active=True,
                    stock_quantity__gt=0
                )[:3]  # Limit to top 3 matches
                found_products.extend(matching_products)
            
            if found_products:
                product_list = ", ".join([p.name for p in found_products[:3]])
                return f"Great choice! I found these {products[0]} options for you: {product_list}. Would you like to know more about any specific item?"
            else:
                return f"I understand you're looking for {products[0]}. Let me check our current inventory and connect you with our team for the latest availability."
        except:
            return f"I'd love to help you find {products[0]}! Let me connect you with our product specialists who can show you our best options."
    
    def handle_order_status_inquiry(self, numbers: List[str], conversation: ChatConversation) -> str:
        """Handle order status inquiries"""
        if not numbers:
            return "I'd be happy to help track your order! Could you please share your order number?"
        
        order_number = numbers[0]
        try:
            # Try to find order by ID or order number
            order = Order.objects.filter(id=order_number).first()
            if order:
                status_messages = {
                    'pending': 'Your order is confirmed and being prepared',
                    'processing': 'Your order is being processed in our facility',
                    'shipped': 'Your order has been shipped and is on the way',
                    'delivered': 'Your order has been delivered successfully',
                    'cancelled': 'Your order has been cancelled'
                }
                status_msg = status_messages.get(order.status, 'Your order is being processed')
                return f"Order #{order_number}: {status_msg}. Expected delivery: {order.delivery_date or 'TBD'}."
            else:
                return f"I couldn't find order #{order_number} in our system. Please check the number or contact our support team for detailed tracking."
        except:
            return f"Let me help you track order #{order_number}. I'll connect you with our order management team for real-time updates."
    
    def handle_pricing_inquiry(self, products: List[str]) -> str:
        """Handle pricing inquiries"""
        try:
            product_name = products[0]
            matching_products = Product.objects.filter(
                name__icontains=product_name,
                is_active=True
            )[:2]
            
            if matching_products:
                price_info = []
                for product in matching_products:
                    price_info.append(f"{product.name}: ₹{product.price}")
                
                return f"Here are the current prices for {product_name}:\n" + "\n".join(price_info) + "\n\nPrices may vary based on quantity and current offers!"
            else:
                return f"I'll get you the latest pricing for {product_name}. Our team will provide you with current rates and any available discounts."
        except:
            return f"Let me get you the best pricing information for {products[0]}. Our team will share current rates and special offers with you."
    
    def handle_availability_inquiry(self, products: List[str]) -> str:
        """Handle availability inquiries"""
        try:
            product_name = products[0]
            available_products = Product.objects.filter(
                name__icontains=product_name,
                is_active=True,
                stock_quantity__gt=0
            )
            
            if available_products:
                return f"Good news! {product_name.title()} is currently available. We have {available_products.count()} options in stock. Would you like to see them?"
            else:
                return f"I'm checking availability for {product_name}. It might be temporarily out of stock, but I'll connect you with our team for the latest updates and alternatives."
        except:
            return f"Let me check the current availability of {products[0]} for you. Our inventory team will provide real-time stock information."
    
    def handle_store_location_inquiry(self, message: str) -> str:
        """Handle store location inquiries"""
        try:
            # Extract location from message
            location_keywords = ['near', 'in', 'at', 'around', 'close to']
            message_lower = message.lower()
            
            for keyword in location_keywords:
                if keyword in message_lower:
                    # Try to find stores
                    stores = Store.objects.filter(is_active=True)[:3]
                    if stores:
                        store_info = []
                        for store in stores:
                            store_info.append(f"{store.name}: {store.address}")
                        return "Here are our store locations:\n" + "\n".join(store_info) + "\n\nWould you like directions to any specific location?"
            
            return "I can help you find our nearest store! Could you please tell me your area or preferred location?"
        except:
            return "I'd love to help you find our stores nearby! Let me connect you with our location team for detailed information and directions."
    
    def handle_complaint(self, message: str) -> str:
        """Handle complaints with empathy and escalation"""
        complaint_keywords = ['wrong', 'bad', 'terrible', 'awful', 'disappointed', 'angry', 'frustrated']
        severity = sum(1 for keyword in complaint_keywords if keyword in message.lower())
        
        if severity >= 2:
            return "I sincerely apologize for this experience. This is clearly important, and I want to ensure it's resolved immediately. I'm escalating this to our senior support manager who will contact you within 15 minutes."
        else:
            return "I'm sorry to hear about this issue. Your feedback is valuable to us. Please share more details so I can help resolve this quickly, or would you prefer to speak with our support supervisor?"
    
    def get_smart_response(self, message: str, conversation: ChatConversation) -> str:
        """Main method to get intelligent bot response"""
        # Clean and prepare message
        message = message.strip()
        if not message:
            return "I'm here to help! What would you like to know about our meat and seafood products?"
        
        # Check for existing bot responses first (admin-defined responses)
        existing_response = self.check_existing_bot_responses(message)
        if existing_response:
            return existing_response
        
        # Generate contextual AI response
        ai_response = self.get_contextual_response(message, conversation)
        
        return ai_response
    
    def check_existing_bot_responses(self, message: str) -> Optional[str]:
        """Check for existing admin-defined bot responses"""
        try:
            message_lower = message.lower()
            bot_responses = BotResponse.objects.filter(is_active=True).order_by('-priority')
            
            for bot_response in bot_responses:
                keywords = bot_response.get_keywords_list()
                if any(keyword in message_lower for keyword in keywords):
                    return bot_response.response
        except:
            pass
        return None


# Initialize global chatbot instance
enhanced_chatbot = EnhancedChatbot()


def get_ai_response(message: str, conversation: ChatConversation) -> Tuple[str, bool]:
    """
    Get AI-powered response from enhanced chatbot
    Returns: (response_text, should_escalate_to_agent)
    """
    try:
        response = enhanced_chatbot.get_smart_response(message, conversation)
        
        # Determine if should escalate based on complexity or keywords
        escalation_keywords = ['speak to manager', 'human agent', 'not satisfied', 'escalate', 'supervisor']
        should_escalate = any(keyword in message.lower() for keyword in escalation_keywords)
        
        return response, should_escalate
        
    except Exception as e:
        # Fallback response if AI fails
        fallback_response = "I want to make sure you get the best help possible. Let me connect you with our support team right away."
        return fallback_response, True
