from django import template

register = template.Library()


@register.filter
def get_confirmed_count(event):
    """Get count of confirmed guests for an event"""
    return event.guests.filter(confirmed=True).count()


@register.filter
def get_pending_count(event):
    """Get count of pending guests for an event"""
    return event.guests.filter(confirmed=False).count()


@register.filter
def get_guest_count(event):
    """Get total count of guests for an event"""
    return event.guests.count()
