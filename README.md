# OBG_Chabanas
Chabanas django server for Online Boardgames


## API de maintenance des game_json

Deux routes POST, sans slash final, accessibles sur l'API interne Chabanas
(`http://localhost:12000` en local) :

- `/game/json/get` : `{"game_name": "Jeux_et_Strategies", "variant_name": "aboukir"}`.
- `/game/json/update` : les mêmes champs, `game_json` (objet de remplacement)
  et `expected_updated_at` (valeur exacte reçue lors de la lecture).

`variant_name` absent ou `default` désigne le jeu de base. La réponse contient
`key`, `game_name`, `variant_name`, `game_json` et `updated_at`. Le JSON est la
définition brute ; les options de session ne sont pas injectées. Les entrées
inactives sont accessibles. Une cible inconnue donne 404 ; elle n'est pas créée.

Chaque appel exige l'en-tête `X-OBG-Admin-Secret`, égal à `OBG_ADMIN_SECRET`
configuré sur Chabanas. Un secret absent côté serveur désactive l'API (503) ;
un secret incorrect donne 403. Le secret n'est pas transmis dans l'URL ni
journalisé. Cette authentification par en-tête permet les appels sans cookie
Django ni jeton CSRF. Les routes restent internes, comme les autres `/game/` ;
aucune règle nginx publique n'est ajoutée.

L'écriture remplace uniquement `game_json` et `updated_at`. Options, activation,
limites de joueurs et sessions ne sont pas modifiées. Le JSON doit être un
objet ; son schéma de composants reste validé par Tourtoirac. Le contrôle de
révision et l'écriture ont lieu sous verrou de ligne dans une transaction :
une révision périmée donne 409 et n'écrit rien. Un remplacement identique ne
change pas la date. Aucune migration de schéma n'est nécessaire pour ces routes.

Client autonome, depuis `OBG/`, après reconstruction/redémarrage de Chabanas
avec ces sources et définition du secret dans l'environnement du client :

```bash
python3 Chabanas/scripts/game_json_api.py get --game Jeux_et_Strategies --variant aboukir
python3 Chabanas/scripts/game_json_api.py update --game Jeux_et_Strategies --variant aboukir --file Games/Jeux_et_Strategies/aboukir/game_json.json
```

Le client lit `OBG_ADMIN_SECRET` et utilise `OBG_CHABANAS_URL` (défaut
`http://localhost:12000`, surcharge possible avec `--url`). Il lit la révision
courante avant l'écriture et ne réessaie pas automatiquement en cas de conflit.
Il ne modifie pas les fichiers sources. Une lecture de contrôle par `get`
permet de récupérer la définition enregistrée.

Tests : `python3 manage.py test Game.test_json_api` (Django/PostgreSQL requis).
