from django import forms

from Contact.models import MESSAGE_MAX_LENGTH


class ContactForm(forms.Form):
    email = forms.EmailField(required=False, label='Email (optionnel)',
                             error_messages={'invalid': 'Adresse email invalide.'})
    text = forms.CharField(label='Message', max_length=MESSAGE_MAX_LENGTH, widget=forms.Textarea,
                           error_messages={
                               'required': 'Le message est vide.',
                               'max_length': f'Le message dépasse {MESSAGE_MAX_LENGTH} caractères.',
                           })
    # trap for robots: hidden from people, a filled one means the message is dropped
    website = forms.CharField(required=False)
