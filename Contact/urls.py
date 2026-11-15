from django.urls import path

from Contact import views

# the public contact form, mounted under contact/ (Chabanas/urls.py)
urlpatterns = [
    path("", views.contact_page, name="contact_page"),
]
