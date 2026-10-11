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

poetry run python manage.py test                # 124 tests
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

Clé facultative `URL_PREFIX` (ex. `"/obg"`) : sous-chemin sous lequel un
reverse proxy publie l'admin en retirant ce préfixe. Elle règle
`FORCE_SCRIPT_NAME`, `STATIC_URL` et le chemin des cookies. Absente en local ;
en production l'admin est à `/obg/admin/` (fichiers dans `OBG/deploy/`). Les
routes `game/` et `session/` ne sont pas concernées : Tourtoirac les appelle
toujours à la racine.

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

## Carte du code

Le dépôt fait environ 900 lignes hors tests. Deux applications Django :
`Game` (catalogue) et `Session` (parties).

| Fichier | Contenu |
| ------- | ------- |
| `Chabanas/urls.py` | Montage : `admin/`, `game/` → `Game.urls`, `session/` → `Session.urls` |
| `Chabanas/tools.py` | `validate_request(request, mandatory_values)` : parse le JSON, vérifie les clés, renvoie un `dict` **ou** une `HttpResponse` 400 |
| `Chabanas/params_ext.py` | `DATABASES`, constantes d'erreur, `PARAMS_EXT["GAME_MAX_DURATION"]` (en jours) |
| `Game/models.py` | `Game`, `Variant` (FK vers `Game`) |
| `Game/views.py` | `game_list` uniquement |
| `Game/tools.py` | `return_game_json` : jeu et variantes actives, **sans** `game_json` |
| `Game/admin.py` `widgets.py` | Admin (variantes en inline), `PrettyJSONWidget` |
| `Session/models.py` | `Session` (FK vers `Game`), `Player` (FK vers `Session`) |
| `Session/views.py` | Les 7 vues de session (tableau ci-dessous) |
| `Session/tools.py` | `generate_session_code` (8 caractères `A-Z0-9`), `return_session_json`, `return_player_json`, `is_session_participant` (non utilisé par les vues) |
| `Game/tests.py` `Session/tests.py` | Tests (`Session/tests.py` : environ 1 500 lignes) |

### Routes

Toutes en `POST` avec un corps JSON. Seul client : `Tourtoirac/chabanas.py`,
qui interroge aussi `/game/list` (avec une liste vide) pour attendre que
Chabanas réponde avant d'ouvrir son WebSocket. Le navigateur n'appelle jamais
Chabanas directement.

| Route | Champs requis | Réponse OK | Appelée par Tourtoirac dans |
| ----- | ------------- | ---------- | --------------------------- |
| `/game/list` | — (`game_name_list` facultatif) | 200 `{game_list: [...]}` : sans liste, tous les jeux `active`, triés par nom ; avec liste, ces jeux, actifs ou non | `get_game_list`, `is_ready` (liste vide) |
| `/session/create` | `game_name`, `nickname` (`nationality` si le jeu en déclare) | 201 `{session_key, session_code}` | `create_session` |
| `/session/get` | `session_code` | 200 `{session: ...}`, filtré par `sat_list` | `create_session`, `get_session_info` |
| `/session/list` | — (`game_name_list` facultatif) | 200 `{sessions: {jeu: [...]}}`, une clé par jeu `active` (filtrée par la liste si elle est fournie) | `get_active_sessions` |
| `/session/join` | `session_code`, `nickname` (`nationality` pour un nouveau joueur si le jeu en déclare) | 200, session **à la racine** (pas sous `session`) | `join_session` |
| `/session/update` | `key` | 200 `{status}` ; écrit `game_json` et/ou `started` (seulement `true`, sinon 400) | `update_session_state`, `start_session` |
| `/session/archive` | `key` | 200 `"Success"` en **texte brut** | `archive_session` |
| `/session/get_archive` | `key` | 200, session inactive | — (aucun appelant) |

Codes de refus de `/session/join`, traduits par Tourtoirac en codes d'erreur
WebSocket : 400 rôle invalide, 401 `access_key` ou `key` fausse, 403
spectateurs interdits, 409 session démarrée ou pleine (pour un **nouveau**
joueur : un pseudo déjà assis revient toujours avec sa `key`).

### Flux de données

- **Création** : le `game_json` de la variante (ou du jeu, pour `default`) est
  **copié** dans `Session.game_json`. Ensuite, la session vit seule : modifier
  le jeu dans l'admin ne touche pas les sessions existantes.
- **Sauvegarde** : Tourtoirac renvoie l'état complet des composants par
  `/session/update` quand une session se vide ou est close. Le `game_json`
  d'une session est donc **l'état de la partie**, pas la définition du jeu.
- **Expiration** : `/session/list` désactive au passage les sessions plus
  anciennes que `GAME_MAX_DURATION` jours. Il n'y a pas de tâche planifiée.
- **Spectateurs** : jamais écrits dans `session_players` ; c'est Tourtoirac
  qui les compte.
- **Archivage** : `active=False` et `code=''`. Le code redevient libre.
- **Nationalités** (facultatif) : un `game_json` peut porter, **dans ses
  `options`**, `"nationalities": ["US", "NVA"]` (`Game/tools.py`
  `read_nationalities` ; la clé n'est pas lue à la racine).
  `/game/list` les expose par variante, `return_session_json` par session.
  Quand la liste n'est pas vide, `/session/create` et `/session/join` (nouveau
  joueur seulement) exigent un `nationality` de la liste, sinon **422**
  (`INVALID_NATIONALITY`). Elle est stockée sur le siège (`Player.nationality`,
  `''` quand le jeu n'en a pas) et renvoyée par `return_player_json` (`null`
  si vide). Plusieurs joueurs peuvent partager la même. Un joueur qui revient
  garde celle de son siège ; un spectateur n'en a pas.
- **Démarrage** (`Session.started`, qui remplace `locked`) : passe à `True`
  quand le dernier siège est pris (`start_session_if_full`, à la création et à
  l'adhésion) ou par `/session/update`. Ne repasse jamais à `False`. Une
  session démarrée refuse les nouveaux joueurs mais accepte les spectateurs.

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
