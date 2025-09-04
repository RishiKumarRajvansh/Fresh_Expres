# Management command to populate initial bot responses
from django.core.management.base import BaseCommand
from core.models import BotResponse

class Command(BaseCommand):
    help = 'Populate initial bot responses for enhanced chatbot'
    
    def handle(self, *args, **options):
        bot_responses = [
            {
                'keywords': 'hello,hi,hey,good morning,good afternoon,good evening',
                'response': 'Hello! Welcome to Fresh Express! 🍖🐟 I\'m FreshBot, your personal assistant. How can I help you today?',
                'priority': 10,
                'escalate_to_agent': False
            },
            {
                'keywords': 'hours,timing,open,close,schedule',
                'response': 'Our store hours vary by location, but most of our stores are open from 8:00 AM to 10:00 PM daily. Our online platform is available 24/7 for your convenience! Would you like information about a specific store location?',
                'priority': 8,
                'escalate_to_agent': False
            },
            {
                'keywords': 'delivery,shipping,how long,when will arrive',
                'response': 'We offer multiple delivery options:\n• Express Delivery: 2-4 hours (same day)\n• Standard Delivery: Next day\n• Scheduled Delivery: Choose your preferred time slot\n\nAll deliveries use our cold-chain system to ensure freshness! What delivery option works best for you?',
                'priority': 9,
                'escalate_to_agent': False
            },
            {
                'keywords': 'payment,pay,card,cash,refund,money',
                'response': 'We accept various payment methods:\n• Credit/Debit Cards (Visa, MasterCard, Rupay)\n• Digital Wallets (Paytm, PhonePe, Google Pay)\n• UPI Payments\n• Cash on Delivery\n• Net Banking\n\nAll payments are processed securely. Need help with a specific payment method?',
                'priority': 8,
                'escalate_to_agent': False
            },
            {
                'keywords': 'fresh,quality,how fresh,guarantee',
                'response': 'Quality and freshness are our top priorities! 🌟\n• Daily fresh arrivals from trusted suppliers\n• Cold storage chain maintained throughout\n• Quality checks at multiple stages\n• 100% freshness guarantee\n• Easy returns if not satisfied\n\nYour satisfaction is guaranteed!',
                'priority': 9,
                'escalate_to_agent': False
            },
            {
                'keywords': 'chicken,poultry,hen,broiler',
                'response': 'We have an excellent selection of fresh chicken! 🐔\n• Farm-fresh broiler chicken\n• Free-range country chicken\n• Organic chicken options\n• Ready-to-cook cuts available\n• Whole chicken and parts\n\nWould you like to see our current chicken varieties and prices?',
                'priority': 7,
                'escalate_to_agent': False
            },
            {
                'keywords': 'fish,seafood,salmon,tuna,prawns,crab',
                'response': 'Fresh from the waters! 🐟🦐 Our seafood selection includes:\n• Daily fresh fish varieties\n• Premium salmon and tuna\n• Live and fresh prawns\n• Crab, lobster, and shellfish\n• Cleaned and ready-to-cook options\n\nWhat type of seafood are you looking for today?',
                'priority': 7,
                'escalate_to_agent': False
            },
            {
                'keywords': 'beef,mutton,lamb,goat,red meat',
                'response': 'Our premium red meat collection includes: 🥩\n• Fresh beef cuts (various grades)\n• Tender mutton and lamb\n• Goat meat (chevon)\n• Marinated and ready-to-cook options\n• Custom cutting available\n\nAll meats are sourced from certified suppliers. Which cut interests you?',
                'priority': 7,
                'escalate_to_agent': False
            },
            {
                'keywords': 'price,cost,expensive,cheap,discount,offer,deal',
                'response': 'We offer competitive prices for premium quality! 💰\n• Daily special offers\n• Bulk purchase discounts\n• Member exclusive deals\n• Seasonal promotions\n• Price matching on select items\n\nWhat specific products are you interested in? I can check current pricing and offers!',
                'priority': 8,
                'escalate_to_agent': False
            },
            {
                'keywords': 'order,track,tracking,status,where is my order',
                'response': 'I can help you track your order! 📦 Please provide:\n• Your order number, or\n• The phone number/email used for the order\n\nI\'ll get you the latest status and delivery updates right away!',
                'priority': 9,
                'escalate_to_agent': False
            },
            {
                'keywords': 'cancel,return,refund,exchange,problem,issue',
                'response': 'I\'m sorry to hear about the issue. We want to make this right! 🔄\n• Easy cancellation before dispatch\n• Hassle-free returns within 24 hours\n• Full refund for quality issues\n• Quick exchange options\n\nPlease share your order details and specific concern so I can assist you better.',
                'priority': 10,
                'escalate_to_agent': True
            },
            {
                'keywords': 'recipe,cook,cooking,marinate,prepare,how to',
                'response': 'Love to cook? I can share some delicious recipes! 👩‍🍳\n• Quick weekday meals\n• Special occasion dishes\n• Marination tips\n• Cooking techniques\n• Spice recommendations\n\nWhich meat or seafood would you like recipe ideas for?',
                'priority': 6,
                'escalate_to_agent': False
            },
            {
                'keywords': 'store,location,address,near me,branch,where',
                'response': 'Find a store near you! 📍 I can help you locate:\n• Nearest store locations\n• Store addresses and contact\n• Driving directions\n• Store-specific timings\n• Available services at each location\n\nWhich area are you looking for stores in?',
                'priority': 7,
                'escalate_to_agent': False
            },
            {
                'keywords': 'account,profile,login,register,password,sign up',
                'response': 'Account assistance is here! 👤\n• Create new account easily\n• Reset forgotten passwords\n• Update profile information\n• Manage delivery addresses\n• View order history\n\nWhat specific account help do you need?',
                'priority': 7,
                'escalate_to_agent': False
            },
            {
                'keywords': 'thank you,thanks,great,good,excellent,awesome',
                'response': 'Thank you so much for your kind words! 😊 We\'re thrilled you\'re happy with our service. Your satisfaction is our greatest reward! Is there anything else I can help you with today?',
                'priority': 5,
                'escalate_to_agent': False
            },
            {
                'keywords': 'bye,goodbye,see you,exit,quit,done',
                'response': 'Thank you for choosing Fresh Express! 👋 Have a wonderful day and happy cooking! Feel free to return anytime for premium quality products. Take care! 🍖🐟',
                'priority': 5,
                'escalate_to_agent': False
            },
        ]
        
        created_count = 0
        for response_data in bot_responses:
            bot_response, created = BotResponse.objects.get_or_create(
                keywords=response_data['keywords'],
                defaults={
                    'response': response_data['response'],
                    'priority': response_data['priority'],
                    'escalate_to_agent': response_data['escalate_to_agent'],
                    'is_active': True
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} bot responses')
        )
