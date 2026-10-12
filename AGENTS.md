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
poetry run ruff check .                         # linter

poetry run python manage.py test                # full Django test suite
poetry run coverage run manage.py test
poetry run coverage html                        # coverage report
poetry run python manage.py collectstatic --noinput  # collect admin assets into static/
poetry run python manage.py sync_game_json jeux.json --dry-run  # preview without writing
```

**pytest n'est PAS une dépendance ici.** Utiliser `manage.py test`.

Lancer ces commandes depuis `OBG/Chabanas/`. Dans cet environnement WSL,
Python 3.14 est disponible, mais Poetry, Django, psycopg et PostgreSQL sont
absents : la suite ne peut pas être exécutée ici. Ne pas annoncer de tests
réussis sans les avoir lancés.

Les tests utilisent `django.test.TestCase` et `RequestFactory`, dans
`Chabanas/tests.py`, `Game/tests.py` et `Session/tests.py` ; nommer les méthodes
`test_<comportement>`. Au 12/10/2026, le code contient **138 méthodes de test**
(6 + 30 + 102), dénombrées sans exécution. Pour cibler un cas :
`poetry run python manage.py test Game.tests.SyncGameJsonTest`.
Aucun seuil de couverture n'est configuré ; `.coveragerc` exclut notamment
modèles, tests, migrations, configuration et admin. Ruff exclut les fichiers
`tests.py`, `__init__.py` et les migrations ; aucun formateur n'est configuré.
`pylyzer` est aussi déclaré comme dépendance, sans configuration dédiée.

Il n'y a **aucune CI** dans ce dépôt : ces commandes sont le seul garde-fou.

## Base de données

`Chabanas/params_ext.py` est un **dictionnaire Python en dur**, importé par
`settings.py` au moment du chargement. Ce n'est pas un fichier `.env`.

Clé facultative `URL_PREFIX` (ex. `"/obg"`) : sous-chemin sous lequel un
reverse proxy publie l'admin en retirant ce préfixe. Elle règle
`FORCE_SCRIPT_NAME`, `STATIC_URL` et le chemin des cookies ; elle donne aussi
aux cookies les noms `chabanas_sessionid` et `chabanas_csrftoken` pour éviter
les collisions avec un autre site Django sur le même hôte. Absente en local ;
en production l'admin est à `/obg/admin/` (fichiers dans `OBG/deploy/`). Les
routes `game/` et `session/` ne sont pas concernées : Tourtoirac les appelle
toujours à la racine.

```python
PARAMS_EXT['DATABASES']['default'] = {
    'ENGINE': 'django.db.backends.postgresql_psycopg2',
    'NAME': 'chabanas', 'USER': 'django',
    'PASSWORD': os.getenv('DB_PASSWORD', '<valeur par défaut dans params_ext.py>'),
    'HOST': os.getenv('DB_HOST', 'localhost'),
    'PORT': os.getenv('DB_PORT', '12432'),
    'OPTIONS': {'application_name': 'chabanas'},
}
```

Seuls `DB_PASSWORD`, `DB_HOST` et `DB_PORT` viennent de l'environnement. Tout
le reste (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, CORS) est figé dans le code
— ne pas lire ces valeurs comme si elles étaient configurables par déploiement.
Les réglages de cookies sont lus dans `PARAMS_EXT` avec des valeurs par défaut
dans `settings.py` : `SESSION_COOKIE_SECURE` et `CSRF_COOKIE_SECURE` valent
`True`. Pour utiliser l'admin en HTTP local, les mettre à `False` dans la
configuration locale ; les garder à `True` pour l'admin publié en HTTPS.

## Carte du code

Deux applications Django :
`Game` (catalogue) et `Session` (parties).

| Fichier | Contenu |
| ------- | ------- |
| `Chabanas/urls.py` | Montage : `admin/`, `game/` → `Game.urls`, `session/` → `Session.urls` |
| `Chabanas/tools.py` | `validate_request(request, mandatory_values)` : parse le JSON, vérifie les clés, renvoie un `dict` **ou** une `HttpResponse` 400 |
| `Chabanas/params_ext.py` | `DATABASES`, constantes d'erreur, `PARAMS_EXT["GAME_MAX_DURATION"]` (en jours) |
| `Game/models.py` | `Game`, `Variant` (FK vers `Game`) |
| `Game/views.py` | `game_list` uniquement |
| `Game/tools.py` | `return_game_json` : jeu et variantes actives, **sans** `game_json` ; `starting_game_json` : le `game_json` de départ d'une session |
| `Game/management/commands/sync_game_json.py` | Recopie le `game_json` des jeux et variantes depuis un document JSON (fichier ou entrée standard `-`), par `key`, avec `--dry-run` ; un jeu ou une variante inconnus sont créés `active=False`, `options` vide. Les `options` ne sont jamais recopiées. Appelée par `OBG/deploy.sh gamejson` |
| `Game/admin.py` `widgets.py` | Admin (variantes en inline), `PrettyJSONWidget` |
| `Session/models.py` | `Session` (FK vers `Game`), `Player` (FK vers `Session`) |
| `Session/views.py` | Les 7 vues de session (tableau ci-dessous) |
| `Session/tools.py` | `generate_session_code` (8 caractères `A-Z0-9`), `return_session_json`, `return_player_json`, `seat_nationality`, `start_session_if_full`, `is_session_participant` (non utilisé par les vues) |
| `Chabanas/tests.py` `Game/tests.py` `Session/tests.py` | Validation des requêtes, modèles, sérialisation, vues, widget JSON et synchronisation |
| `Game/static/Game/` | CSS et JavaScript de `PrettyJSONWidget` ; pas d'assets de jeux dans ce dépôt |
| `Game/migrations/0005_game_type.py` | Ajoute `Game.game_type` (`Boardgame` ou `Wargame`, `Wargame` par défaut) ; `return_game_json` le renvoie sous la clé `type`, que le lobby de Raffaillac lit pour ses onglets. `sync_game_json` ne le recopie pas |
| `Game/migrations/0004_fix_positions_boolean.py` | Convertit `options.fix_positions` en booléen sur les jeux et variantes ; ne touche pas aux sessions existantes |

### Routes

Toutes en `POST` avec un corps JSON. Seul client : `Tourtoirac/chabanas.py`,
qui interroge aussi `/game/list` (avec une liste vide) pour attendre que
Chabanas réponde avant d'ouvrir son WebSocket. Le navigateur n'appelle jamais
Chabanas directement.

| Route | Champs requis | Réponse OK | Appelée par Tourtoirac dans |
| ----- | ------------- | ---------- | --------------------------- |
| `/game/list` | — (`game_name_list` facultatif) | 200 `{game_list: [...]}` : sans liste, tous les jeux `active`, triés par nom ; avec liste, ces jeux, actifs ou non | `get_game_list`, `is_ready` (liste vide) |
| `/session/create` | `game_name`, `nickname` (`nationality` si le jeu en déclare) | 201 `{session_key, session_code}` | `create_session` |
| `/session/get` | `session_code` | 200 `{session: ...}`, détails optionnels via `sat_list` | `create_session`, `get_session_info` |
| `/session/list` | — (`game_name_list` facultatif) | 200 `{sessions: {jeu: [...]}}`, une clé par jeu `active` (filtrée par la liste si elle est fournie) | `get_active_sessions` |
| `/session/join` | `session_code`, `nickname` (`nationality` pour un nouveau joueur si le jeu en déclare) | 200, session **à la racine** (pas sous `session`) | `join_session` |
| `/session/update` | `key` | 200 `{status: "success"}` ; écrit un `game_json` non vide et/ou `started: true` (autre valeur non nulle : 400) | `update_session_state`, `start_session` |
| `/session/archive` | `key` | 200 `"Success"` en **texte brut** | `archive_session` |
| `/session/get_archive` | `key` | 200, session inactive à la racine, avec `game_json` | — (aucun appelant) |

Codes de refus de `/session/join`, traduits par Tourtoirac en codes d'erreur
WebSocket : 400 rôle invalide, 401 `access_key` ou `key` fausse, 403
spectateurs interdits, 409 session démarrée ou pleine (pour un **nouveau**
joueur : un pseudo déjà assis revient toujours avec sa `key`).

### Flux de données

- **Création** : le `game_json` de la variante (ou du jeu, pour `default`) est
  **copié** dans `Session.game_json`, et son bloc `options` y est **remplacé**
  par le champ `options` de cette variante ou de ce jeu (`Game/tools.py`
  `starting_game_json`). Un `options` resté dans le `game_json` d'un jeu n'est
  donc jamais utilisé. Ensuite, la session vit seule : modifier le jeu dans
  l'admin ne touche pas les sessions existantes.
- **Sauvegarde** : Tourtoirac renvoie l'état complet des composants par
  `/session/update` quand une session se vide ou est close. Le `game_json`
  d'une session est donc **l'état de la partie**, pas la définition du jeu.
- **Expiration** : `/session/list` désactive au passage les sessions plus
  anciennes que `GAME_MAX_DURATION` jours. Il n'y a pas de tâche planifiée.
- **Spectateurs** : jamais écrits dans `session_players` ; c'est Tourtoirac
  qui les compte.
- **Archivage** : `active=False` et `code=''`. Le code redevient libre.
- **Nationalités** (facultatif) : le champ `options` d'un jeu ou d'une
  variante peut porter `"nationalities": ["US", "NVA"]` (`Game/tools.py`
  `options_nationalities` ; `read_nationalities` lit la même clé dans le
  `game_json` d'une session).
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

- Python : indentation de **4 espaces**, fonctions et variables en `snake_case`,
  classes en `PascalCase`. Préserver les fins de ligne des fichiers existants
  (beaucoup sont en CRLF).
- Commentaires et docstrings **en anglais**.
- Vues **fonctionnelles**, décorées dans cet ordre :
  `@csrf_exempt` puis `@require_http_methods([...])`.
- Docstrings au format Sphinx : `:param request:`, `:type request:`,
  `:return:`, `:rtype:`.
- Les erreurs sont des **`HttpResponse` en texte brut** avec les constantes de
  `params_ext.py` (`BAD_REQUEST`, `FORBIDDEN`, `FORBIDDEN_METHOD`, `CONFLICT`,
  `UNAUTHORIZED`, `INVALID_NATIONALITY`). Certaines erreurs 409 utilisent un
  message littéral ; les décorateurs renvoient 405 et `get_object_or_404` 404.
  Les vues n'utilisent pas les réponses d'erreur DRF, malgré DRF installé.
- Logger par module : `logger = logging.getLogger(__name__)`.
- Sérialisation dans `<App>/tools.py` (`return_game_json`,
  `return_session_json`, `return_player_json`), jamais dans les vues.

### `sat_list` (mécanisme de saturation)

Les sérialiseurs de `Session/tools.py` exposent les champs usuels par défaut.
`sat_list` ajoute uniquement les détails optionnels : `game_json` pour la
session, `key` pour un joueur ; `player_key` sur la session propage `key` aux
joueurs. Ce n'est pas un filtre de tous les champs de la réponse.

```python
if 'game_json' in sat_list:      # game_json seulement sur demande explicite
if 'player_key' in sat_list:     # propagé aux joueurs via player_sat_list
```

`access_key` est renvoyé par `return_session_json` sans être conditionné —
ajouter un champ « sensible » exige donc de le passer par `sat_list` dès le départ.

### Modèles

`db_table` fixé à la main (`game`, `game_variant`, `session`,
`session_players`), `objects = models.Manager()`, et `Meta.indexes` sous forme
de **tuple**. `Game`, `Variant` et `Session` ont une `key` UUID
(`default=uuid.uuid1`, `editable=False`). **`Player.key` est un `CharField`
nullable**, fourni par le client, vide par défaut : ce n'est pas un UUID généré.
Les champs facultatifs ont `blank=True` (`options`, `code`, `access_key`,
`nationality`…) ; `Game.clean` et `Variant.clean` normalisent `options=None`
en `{}` pour les formulaires d'admin.

## Points d'attention

- **Le schéma des composants de `game_json` n'est pas validé ici.** Le
  `JSONField` et le widget vérifient la syntaxe JSON ; `sync_game_json` exige
  un objet et contrôle son document d'import. La validation des composants
  revient à `Tourtoirac`. Toute évolution du contrat doit être répercutée dans
  les trois dépôts.
- **Une variante n'hérite pas du jeu de base.** `Variant.game_json` *remplace*
  `Game.game_json`, et `Variant.options` *remplace* `Game.options` : le contenu
  n'est jamais fusionné. Toute donnée placée
  uniquement au niveau du jeu (ex. `setup`) est invisible depuis une variante.
- **Routes sans slash final** : `POST /game/list`, `POST /session/create`, etc.
- `return_session_json` **mute** `session.game_json` en y injectant une clé
  `game` quand `sat_list` contient `game_json`. L'attribut d'instance est
  modifié en mémoire, sans sauvegarde automatique en base.
- `Game/urls.py` n'expose aujourd'hui que `list`. Ajouter une route = vue +
  entrée `urlpatterns` avec un `name=`.
- `Game/widgets.py` contient `PrettyJSONWidget`, un formulaire d'édition JSON
  enrichi pour l'admin Django.
- `settings.py` force le niveau `DEBUG` sur le logger racine : les tests sont
  verbeux.
- `sync_game_json` attend `{"games": [...], "variants": [...]}` et traite
  l'import dans une transaction. Une ligne connue ne reçoit que `game_json`
  et `updated_at` ; ses options et métadonnées restent locales. Un nom de jeu
  déjà pris sous une autre clé ou une variante sans jeu connu sont ignorés.
- La migration `0004` transforme `options.fix_positions` : `null` → `false`,
  toute autre valeur non booléenne → `true`. Les anciennes sessions conservent
  leurs valeurs ; le retour arrière ne restaure pas les coordonnées.

## Docker

`python:3.14-slim`, Poetry 2.1.3 installé via le script officiel,
`poetry install --no-root`, `EXPOSE 80`.

Le `CMD` du **Dockerfile seul** lance `manage.py runserver 0.0.0.0:80`.
En revanche, `OBG/deploy/docker-compose.yml` remplace cette commande par
`collectstatic`, puis `migrate`, puis **Gunicorn avec les workers gevent**
(`Chabanas.wsgi`, port 80). Vérifier la commande du déploiement concerné
avant de diagnostiquer le serveur.
