from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from Contact.models import MESSAGE_MAX_LENGTH, Message
from Contact.views import MAX_MESSAGES_PER_HOUR


class ContactFormTestCase(TestCase):
    def send(self, ip='1.2.3.4', **data):
        body = {'email': '', 'text': 'Bonjour', 'website': ''}
        body.update(data)
        return self.client.post(reverse('contact_page'), body, HTTP_X_REAL_IP=ip)

    def test_page(self):
        response = self.client.get(reverse('contact_page'))
        self.assertContains(response, "Remplissez le formulaire pour envoyer un message à l'administrateur.")
        self.assertContains(response, 'Email (optionnel)')
        self.assertContains(response, 'Envoyer')

    def test_send_without_email(self):
        response = self.send(text='  Un message  ')
        self.assertContains(response, 'Message envoyé, merci.')
        self.assertContains(response, 'Retour au lobby')
        message = Message.objects.get()
        self.assertEqual(message.text, 'Un message')
        self.assertEqual(message.email, '')
        self.assertEqual(message.ip, '1.2.3.4')
        self.assertFalse(message.read)

    def test_send_with_email(self):
        self.send(email='joueur@example.com')
        self.assertEqual(Message.objects.get().email, 'joueur@example.com')

    def test_invalid(self):
        self.assertContains(self.send(email='pas-un-email'), 'Adresse email invalide.')
        self.assertContains(self.send(text=''), 'Le message est vide.')
        self.assertContains(self.send(text='x' * (MESSAGE_MAX_LENGTH + 1)), 'dépasse')
        self.assertFalse(Message.objects.exists())

    def test_trap_drops_the_message(self):
        response = self.send(website='http://spam.example')
        self.assertContains(response, 'Message envoyé, merci.')
        self.assertFalse(Message.objects.exists())

    def test_limit_per_hour(self):
        for _ in range(MAX_MESSAGES_PER_HOUR):
            self.send()
        response = self.send()
        self.assertContains(response, 'Trop de messages')
        self.assertEqual(Message.objects.count(), MAX_MESSAGES_PER_HOUR)
        # another address is not limited
        self.assertContains(self.send(ip='5.6.7.8'), 'Message envoyé')
        # an hour later, the first one may write again
        Message.objects.update(created_at=timezone.now() - timedelta(hours=2))
        self.assertContains(self.send(), 'Message envoyé')


class ManageMessagesTestCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', password='pw', is_staff=True)
        self.client.force_login(self.staff)
        now = timezone.now()
        self.old_unread = Message.objects.create(text='ancien non lu ' + 'a' * 200)
        self.new_unread = Message.objects.create(text='récent non lu', email='a@example.com')
        self.read = Message.objects.create(text='déjà lu', read=True)
        Message.objects.filter(pk=self.old_unread.pk).update(created_at=now - timedelta(days=2))
        Message.objects.filter(pk=self.new_unread.pk).update(created_at=now - timedelta(days=1))
        Message.objects.filter(pk=self.read.pk).update(created_at=now)

    def test_staff_only(self):
        self.client.logout()
        for url in (reverse('manage_messages_page'), reverse('manage_message_page', args=[self.read.pk])):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.post(reverse('manage_message_delete', args=[self.read.pk]))
        self.assertTrue(Message.objects.filter(pk=self.read.pk).exists())

    def test_list_order_preview_and_envelope(self):
        response = self.client.get(reverse('manage_messages_page'))
        page = response.content.decode()
        self.assertLess(page.index('récent non lu'), page.index('ancien non lu'))
        self.assertLess(page.index('ancien non lu'), page.index('déjà lu'))
        preview = response.context['messages_list'][1]['preview']
        self.assertEqual(len(preview), 101)
        self.assertEqual([m['email'] for m in response.context['messages_list']], [True, False, False])
        self.assertContains(response, '✉', count=1)

    def test_unread_count_in_every_menu(self):
        for name in ('manage_page', 'manage_refereed_page', 'manage_maintenance_page', 'manage_messages_page'):
            self.assertContains(self.client.get(reverse(name)), 'Messages (2)')

    def test_detail_does_not_mark_read(self):
        response = self.client.get(reverse('manage_message_page', args=[self.new_unread.pk]))
        self.assertContains(response, 'Retour à la liste')
        self.assertContains(response, 'a@example.com')
        self.assertContains(response, 'Marquer comme lu')
        self.assertContains(response, 'Supprimer')
        self.new_unread.refresh_from_db()
        self.assertFalse(self.new_unread.read)

    def test_read_message_has_no_mark_button(self):
        response = self.client.get(reverse('manage_message_page', args=[self.read.pk]))
        self.assertNotContains(response, 'Marquer comme lu')
        self.assertContains(response, 'Supprimer')

    def test_mark_read(self):
        response = self.client.post(reverse('manage_message_read', args=[self.new_unread.pk]))
        self.assertRedirects(response, reverse('manage_messages_page'))
        self.new_unread.refresh_from_db()
        self.assertTrue(self.new_unread.read)

    def test_delete(self):
        response = self.client.post(reverse('manage_message_delete', args=[self.old_unread.pk]))
        self.assertRedirects(response, reverse('manage_messages_page'))
        self.assertFalse(Message.objects.filter(pk=self.old_unread.pk).exists())

    def test_actions_need_post(self):
        self.assertEqual(self.client.get(reverse('manage_message_read', args=[self.new_unread.pk])).status_code, 405)
