from django.db import models

# longest message accepted by the contact form
MESSAGE_MAX_LENGTH = 5000


class Message(models.Model):
    """
    A message sent to the administrator by the contact form of the lobby
    (public page contact/), read on the administration pages manage/messages/.
    """
    # empty when the sender does not wish to be contacted
    email = models.EmailField(blank=True, default='')
    text = models.TextField(max_length=MESSAGE_MAX_LENGTH)
    # the sender's address, kept for the limit of messages per hour only (never shown)
    ip = models.GenericIPAddressField(null=True, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager()

    class Meta:
        db_table = 'contact_message'
        # unread first, then the most recent first
        ordering = ('read', '-created_at')

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} - {self.text[:40]}"
