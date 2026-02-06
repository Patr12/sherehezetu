import threading
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Guest, Event
from .utils import generate_invitation_card
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

def send_invitation_email(guest):
    generate_invitation_card(guest)

    subject = f"Invitation: {guest.event.title}"
    context = {
        "guest": guest,
        "event": guest.event,
        "confirm_url": f"https://{settings.DOMAIN}/confirm/{guest.qr_code}/"
    }

    html_content = render_to_string("events/email_invitation.html", context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [guest.email]
    )
    email.attach_alternative(html_content, "text/html")

    if guest.invitation_card:
        email.attach_file(guest.invitation_card.path)

    email.send()
    logger.info(f"Email sent to {guest.email}")


def send_whatsapp_invitation(guest):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    generate_invitation_card(guest)


    body = f"""
Invitation: {guest.event.title}

Dear {guest.full_name}
Date: {guest.event.date.strftime('%d %B %Y')}
Venue: {guest.event.venue}
Dear {guest.full_name}, please find your invitation to {guest.event.title}

Confirm: https://{settings.DOMAIN}/confirm/{guest.qr_code}/
"""
    client.messages.create(
        body=body,
        from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
        to=f"whatsapp:{guest.phone}",
        media_url=[f"https://{settings.DOMAIN}{guest.invitation_card.url}"]
    )
    logger.info(f"WhatsApp sent to {guest.phone}")


def batch_send_invitations(event_id, via="both"):
    """Send invitations to all guests concurrently using threads"""
    event = Event.objects.get(id=event_id)
    threads = []

    for guest in event.guests.all():
        if via in ["email", "both"]:
            t_email = threading.Thread(target=send_invitation_email, args=(guest,))
            threads.append(t_email)
            t_email.start()

        if via in ["whatsapp", "both"]:
            t_whatsapp = threading.Thread(target=send_whatsapp_invitation, args=(guest,))
            threads.append(t_whatsapp)
            t_whatsapp.start()

    # Subiri threads zote kumaliza
    for t in threads:
        t.join()




@shared_task
def generate_all_cards(event_id):
    event = Event.objects.get(id=event_id)

    for guest in event.guests.all():
        generate_invitation_card(guest)
