import json

from django import forms


class PrettyJSONWidget(forms.Textarea):
    """
    Zone de texte pour un champ JSON, lisible et éditable.

    Le contenu est réindenté à l'affichage (Django sérialise les JSONField sans
    indentation), la police est monospace et un bouton côté client reformate et
    valide la saisie. Le serveur reste seul juge du JSON enregistré : le widget
    ne fait que rendre l'édition confortable.
    """

    def __init__(self, attrs=None):
        defaults = {
            "rows": 24,
            "cols": 100,
            "class": "vLargeTextField pretty-json",
            "spellcheck": "false",
            "autocomplete": "off",
        }
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)

    def format_value(self, value):
        if value is None or value == "":
            return value
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                # saisie invalide renvoyée telle quelle : l'utilisateur doit la
                # voir pour la corriger, pas la perdre
                return value
        return json.dumps(value, indent=2, ensure_ascii=False)

    @property
    def media(self):
        return forms.Media(
            css={"all": ["Game/css/pretty_json.css"]},
            js=["Game/js/pretty_json.js"],
        )
