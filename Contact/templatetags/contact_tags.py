from django import template

from Contact.models import Message

register = template.Library()


@register.simple_tag
def unread_messages() -> int:
    """The number of unread messages, shown in the menu of the administration pages."""
    return Message.objects.filter(read=False).count()
