from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.core.mail import send_mail
from django.conf import settings
from .models import ContactMessage

class ImprovedContactView(TemplateView):
    template_name = 'core/contact.html'
    
    def post(self, request, *args, **kwargs):
        # Get form data
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        # Validate required fields
        if not all([name, email, subject, message]):
            return self.get(request, *args, **kwargs)
        
        try:
            # Save to database
            contact_message = ContactMessage.objects.create(
                name=name,
                email=email,
                phone=phone,
                subject=subject,
                message=message
            )
            
            # Send email notification to admin
            admin_subject = f'🍖 New Contact Form: {subject}'
            admin_body = f"""
🍖 NEW CONTACT FORM SUBMISSION - Fresh Express

📋 CUSTOMER DETAILS:
Name: {name}
Email: {email}
Phone: {phone or 'Not provided'}
Subject: {subject}

📝 MESSAGE:
{message}

⏰ Submitted: {contact_message.created_at.strftime('%Y-%m-%d at %H:%M:%S')}

📧 Reply directly to: {email}

---
    Fresh Express Admin Panel
            """
            
            # Send email to admin
            send_mail(
                subject=admin_subject,
                message=admin_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['ritvik.raj.test1@gmail.com'],
                fail_silently=False,
            )
            
            # Send confirmation email to customer
            customer_subject = '🍖 Thank you for contacting Fresh Express!'
            customer_body = f"""
Dear {name},

Thank you for contacting Fresh Express! 🍖

We have successfully received your message regarding: "{subject}"

Our dedicated support team will carefully review your inquiry and respond within 24 hours to your email: {email}

Your message:
"{message}"

In the meantime, you can:
• Browse our fresh products
• Track your orders (if you have any)
• Use our live chat for immediate assistance

We appreciate your interest in our premium meat and seafood products!

Best regards,
The Fresh Express Team 🦐🐟🥩

---
This is an automated confirmation. Please do not reply to this email.
For immediate assistance, visit our website or use live chat.
            """
            
            try:
                send_mail(
                    subject=customer_subject,
                    message=customer_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except:
                pass  # Don't fail if customer email fails
            
        except Exception as e:
            pass  # Handle any errors silently
            
        return redirect('core:contact')
