"""
Contact of the administrator.

The public page contact/, linked from the top of the lobby, sends a message
(an email to answer to, optional, and the text), saved in Contact.models.Message.
Robots are kept out by a hidden trap field and a limit of messages per hour
for a same address.

The administration pages manage/messages/ (staff only) list the messages,
unread first, then show one of them, mark it as read or delete it.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from Contact.forms import ContactForm
from Contact.models import Message

# messages a same address may send in an hour
MAX_MESSAGES_PER_HOUR = 5
# characters of a message shown in the list
PREVIEW_LENGTH = 100


def _client_ip(request) -> str | None:
    """The sender's address: the reverse proxy (nginx) passes it in X-Real-IP."""
    ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or ''
    ip = ip.split(',')[0].strip()
    return ip or None


def _too_many(ip: str | None) -> bool:
    if ip is None:
        return False
    since = timezone.now() - timedelta(hours=1)
    return Message.objects.filter(ip=ip, created_at__gte=since).count() >= MAX_MESSAGES_PER_HOUR


@require_http_methods(["GET", "POST"])
def contact_page(request) -> HttpResponse:
    """
    The contact form: on a valid POST the message is saved and the page says so.
    :param request: Request information
    :type request: Http request
    :return: the page
    :rtype: HttpResponse
    """
    context = {'lobby_url': settings.OBG_SITE_URL, 'sent': False, 'error': ''}
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            ip = _client_ip(request)
            if form.cleaned_data['website']:
                # a robot filled the trap: it is told the message went, nothing is saved
                context['sent'] = True
            elif _too_many(ip):
                context['error'] = "Trop de messages envoyés depuis votre connexion : réessayez dans une heure."
            else:
                Message.objects.create(email=form.cleaned_data['email'], text=form.cleaned_data['text'].strip(), ip=ip)
                context['sent'] = True
    else:
        form = ContactForm()
    context['form'] = form
    return render(request, 'Contact/contact.html', context)


@staff_member_required
@require_http_methods(["GET"])
def manage_messages_page(request) -> HttpResponse:
    """
    The list of the messages, unread first, then the most recent first.
    :param request: Request information
    :type request: Http request
    :return: the page
    :rtype: HttpResponse
    """
    messages = [
        {
            'id': message.id,
            'created_at': message.created_at,
            'preview': message.text[:PREVIEW_LENGTH] + ('…' if len(message.text) > PREVIEW_LENGTH else ''),
            'email': bool(message.email),
            'read': message.read,
        }
        for message in Message.objects.order_by('read', '-created_at')
    ]
    return render(request, 'Contact/manage_messages.html', {'messages_list': messages})


@staff_member_required
@require_http_methods(["GET"])
def manage_message_page(request, message_id: int) -> HttpResponse:
    """
    One message: its email if any, its whole text, and the buttons to delete
    it or mark it as read (opening it does not).
    :param request: Request information
    :type request: Http request
    :param message_id: the id of the message
    :type message_id: int
    :return: the page
    :rtype: HttpResponse
    """
    message = get_object_or_404(Message, pk=message_id)
    return render(request, 'Contact/manage_message.html', {'message': message})


@staff_member_required
@require_POST
def manage_message_read(request, message_id: int) -> HttpResponse:
    """Mark the message as read, then back to the list."""
    Message.objects.filter(pk=message_id).update(read=True)
    return redirect('manage_messages_page')


@staff_member_required
@require_POST
def manage_message_delete(request, message_id: int) -> HttpResponse:
    """Delete the message, then back to the list."""
    Message.objects.filter(pk=message_id).delete()
    return redirect('manage_messages_page')
