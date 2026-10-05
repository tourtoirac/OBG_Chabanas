# Chabanas

Django 6 / DRF — serveur de catalogue et de sessions pour **Online Boardgames**.
Python >= 3.14, Poetry, PostgreSQL.

Ce dépôt est l'un des trois projets frères sous `OBG/` :

| Projet      | Rôle                                              |
| ----------- | ------------------------------------------------- |
| `Chabanas`  | HTTP : catalogue de jeux, création/archivage de session |
| `Tourtoirac`| WebSocket : logique de jeu, état des composants     |
| `Raffaillac`| Frontend TypeScript/Vite                           |

`Tourtoirac` appelle cette API. Modifier un contrat d'API ici impose de
mettre à jour `Tourtoirac` **et** `Raffaillac`.

## Commandes

```bash
poetry install
poetry run python manage.py runserver          # dev
poetry run python manage.py makemigrations
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run ruff check .                         # linter (ruff est la seule dep de lint)

poetry run python manage.py test                # 107 tests
poetry run coverage run manage.py test
poetry run coverage html                        # .coveragerc exclut models/tests/migrations
```

**pytest n'est PAS une dépendance ici.** Utiliser `manage.py test`.

Les tests ont besoin d'un PostgreSQL joignable (§ Base de données). Je n'ai pas
pu les exécuter dans cet environnement (WSL, pas de Postgres) : leur état est
inconnu, alors que `Tourtoirac` et `Raffaillac` sont verts.

Il n'y a **aucune CI** dans ce dépôt : ces commandes sont le seul garde-fou.

## Base de données

`Chabanas/params_ext.py` est un **dictionnaire Python en dur**, importé par
`settings.py` au moment du chargement. Ce n'est pas un fichier `.env`.

```python
DATABASES['default'] = {
    ENGINE: django.db.backends.postgresql_psycopg2,
    NAME: 'chabanas', USER: 'django',
    PASSWORD: os.getenv('DB_PASSWORD', 'a123456789&'),
    HOST:     os.getenv('DB_HOST', 'localhost'),
    PORT:     os.getenv('DB_PORT', '12432'),
}
```

Seuls `DB_PASSWORD`, `DB_HOST` et `DB_PORT` viennent de l'environnement. Tout
le reste (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, CORS) est figé dans le code
— ne pas lire ces valeurs comme si elles étaient configurables par déploiement.

## Conventions

- Commentaires et docstrings **en anglais**.
- Vues **fonctionnelles**, décorées dans cet ordre :
  `@csrf_exempt` puis `@require_http_methods([...])`.
- Docstrings au format Sphinx : `:param request:`, `:type request:`,
  `:return:`, `:rtype:`.
- Les erreurs sont des **`HttpResponse` en texte brut** avec les constantes de
  `params_ext.py` (`BAD_REQUEST`, `FORBIDDEN`, `FORBIDDEN_METHOD`, `CONFLICT`,
  `UNAUTHORIZED`) — **pas** les réponses d'erreur DRF, malgré DRF installé.
- Logger par module : `logger = logging.getLogger(__name__)`.
- Sérialisation dans `<App>/tools.py` (`return_game_json`,
  `return_session_json`, `return_player_json`), jamais dans les vues.

### `sat_list` (mécanisme de saturation)

Les fonctions de `tools.py` acceptent une liste de champs à exposer. Un champ
n'apparaît dans la réponse que s'il est nommément listé.

```python
if 'game_json' in sat_list:      # game_json seulement sur demande explicite
if 'player_key' in sat_list:     # propagé aux joueurs via player_sat_list
```

`access_key` est renvoyé par `return_session_json` sans être conditionné —
ajouter un champ « sensible » exige donc de le passer par `sat_list` dès le départ.

### Modèles

`null=False, blank=False` explicite partout, `db_table` fixé à la main
(`game`, `game_variant`, `session`, `session_players`), `objects = models.Manager()`,
et `Meta.indexes` sous forme de **tuple**. Chaque modèle a un `key` UUID
(`default=uuid.uuid1`, `editable=False`).

## Points d'attention

- **`game_json` n'est jamais validé.** C'est un `JSONField(default=dict)` traité
  comme opaque de bout en bout. Rien dans ce dépôt n'impose son schéma ; c'est
  `Tourtoirac` qui le valide. Ajouter une clé ici ne casse rien, mais rien ne
  la valide non plus.
- **Une variante ne hérite pas du jeu de base.** `Variant.game_json` *remplace*
  `Game.game_json` : le contenu n'est jamais fusionné. Toute donnée placée
  uniquement au niveau du jeu (ex. `setup`) est invisible depuis une variante.
- **Routes sans slash final** : `POST /game/list`, `POST /session/create`, etc.
- `return_session_json` **mute** `session.game_json` en y injectant une clé
  `game` avant de l'assigner. L'attribut d'instance est corrompu pour le reste de
  la requête — ne pas s'appuyer dessus ensuite.
- `Game/urls.py` n'expose aujourd'hui que `list`. Ajouter une route = vue +
  entrée `urlpatterns` avec un `name=`.
- `Game/widgets.py` contient `PrettyJSONWidget`, un formulaire d'édition JSON
  enrichi pour l'admin Django.
- `settings.py` force le niveau `DEBUG` sur le logger racine : les tests sont
  verbeux.

## Docker

`python:3.14-slim`, Poetry 2.1.3 installé via le script officiel,
`poetry install --no-root`, `EXPOSE 80`.

`CMD` lance `manage.py runserver 0.0.0.0:80` — **pas** gunicorn, même si
`gunicorn[gevent]` est déclaré dans `pyproject.toml`. Ne pas supposer un
serveur de production.
