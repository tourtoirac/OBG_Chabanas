from django.contrib import admin

from Contact.models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "email", "read", "text")
    list_filter = ("read",)
    readonly_fields = ("created_at", "ip")
