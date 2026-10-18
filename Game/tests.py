import io
import json
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.shortcuts import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from Game.models import Game, Variant
from Game.tools import return_game_json, starting_game_json
from Game.views import game_list
from Game.widgets import PrettyJSONWidget


class PrettyJSONWidgetTest(TestCase):
    def test_format_value_indents_the_json(self):
        widget = PrettyJSONWidget()
        rendered = widget.format_value('{"b": 2, "a": 1}')
        self.assertEqual(json.loads(rendered), {"b": 2, "a": 1})
        self.assertIn("\n", rendered)

    def test_format_value_keeps_invalid_input_untouched(self):
        widget = PrettyJSONWidget()
        self.assertEqual(widget.format_value("{oops"), "{oops")

    def test_format_value_keeps_an_empty_value(self):
        widget = PrettyJSONWidget()
        self.assertEqual(widget.format_value(""), "")

    def test_media_loads_the_editor_assets(self):
        media = str(PrettyJSONWidget().media)
        self.assertIn("pretty_json.js", media)
        self.assertIn("pretty_json.css", media)


class GameModelTest(TestCase):
    def test_create_game(self):
        game = Game.objects.create(
            name= "Test Game",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "default",
            },
            active=True
        )
        self.assertEqual(game.name, "Test Game")
        self.assertEqual(game.max_players, 2)
        self.assertEqual(game.max_watchers, 10)
        self.assertEqual(game.max_sessions, 5)
        self.assertEqual(game.active, True)
        self.assertEqual(game.game_json, {"game": "default"})
        self.assertEqual(game.__str__(), "Test Game")

    def test_create_variant(self):
        game = Game.objects.create(
            name= "Test Game",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "test",
            },
            active=True
        )
        variant = Variant.objects.create(
            game=game,
            name="Variant Name",
            max_players=3,
            max_watchers=5,
            game_json={
                "game": "variant",
            },
            active=True

        )
        self.assertEqual(variant.name, "Variant Name")
        self.assertEqual(variant.max_players, 3)
        self.assertEqual(variant.max_watchers, 5)
        self.assertTrue(variant.active)
        self.assertEqual(variant.__str__(), "Variant Name")


class ReturnGameJsonTest(TestCase):

    def test_return_game_json_default_variant(self):
        game = Game.objects.create(
            name="waterloo",
            min_players=1,
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={"game": "waterloo"},
            active=True,
        )

        game_data = return_game_json(game)
        self.assertEqual(game_data["key"], game.key)
        self.assertEqual(game_data["name"], "waterloo")
        self.assertEqual(game_data["max_sessions"], 5)
        self.assertEqual(list(game_data["variant"].keys()), ["default"])
        self.assertEqual(game_data["variant"]["default"], {
            "key": game.key,
            "name": "default",
            "display_name": "waterloo",
            "min_players": 1,
            "max_players": 2,
            "max_watchers": 10,
            "nationalities": [],
        })

    def test_return_game_json_carries_the_display_names(self):
        game = Game.objects.create(name="waterloo", display_name="Waterloo 1815", active=True)
        Variant.objects.create(game=game, name="solo", display_name="Solo, against the AI", active=True)
        Variant.objects.create(game=game, name="duel", active=True)

        game_data = return_game_json(game)
        self.assertEqual(game_data["name"], "waterloo")
        self.assertEqual(game_data["display_name"], "Waterloo 1815")
        # the default variant is the game itself: it shows the name of the game
        self.assertEqual(game_data["variant"]["default"]["display_name"], "Waterloo 1815")
        # variants stay keyed by their name: sessions are still created with it
        self.assertEqual(game_data["variant"]["solo"]["display_name"], "Solo, against the AI")
        # an empty display_name falls back on the name
        self.assertEqual(game_data["variant"]["duel"]["display_name"], "duel")

    def test_return_game_json_carries_the_type_of_the_game(self):
        wargame = Game.objects.create(name="typed wargame", game_json={})
        boardgame = Game.objects.create(name="typed boardgame", game_type="Boardgame", game_json={})

        # a game is a wargame unless told otherwise
        self.assertEqual(return_game_json(wargame)["type"], "Wargame")
        self.assertEqual(return_game_json(boardgame)["type"], "Boardgame")

    def test_return_game_json_lists_the_nationalities_of_each_variant(self):
        game = Game.objects.create(
            name="vietnam",
            options={"nationalities": ["US", "NVA", "US", "", 3]},
            active=True,
        )
        Variant.objects.create(game=game, name="short", options={"nationalities": "US"}, active=True)
        # the key is only read in the options field, never in the game_json
        Variant.objects.create(game=game, name="root", game_json={"options": {"nationalities": ["US"]}}, active=True)

        game_data = return_game_json(game)
        # duplicates and anything that is not a name are dropped
        self.assertEqual(game_data["variant"]["default"]["nationalities"], ["US", "NVA"])
        # a variant replaces the options: it does not inherit the list
        self.assertEqual(game_data["variant"]["short"]["nationalities"], [])
        self.assertEqual(game_data["variant"]["root"]["nationalities"], [])

    def test_return_game_json_with_active_variant(self):
        game = Game.objects.create(name="waterloo", active=True)
        variant = Variant.objects.create(
            game=game,
            name="solo",
            min_players=1,
            max_players=3,
            max_watchers=15,
            active=True,
        )

        game_data = return_game_json(game)
        self.assertEqual(sorted(game_data["variant"].keys()), ["default", "solo"])
        self.assertEqual(game_data["variant"]["solo"], {
            "key": variant.key,
            "name": "solo",
            "display_name": "solo",
            "active": True,
            "min_players": 1,
            "max_players": 3,
            "max_watchers": 15,
            "nationalities": [],
        })

    def test_return_game_json_ignores_inactive_variant(self):
        game = Game.objects.create(name="waterloo", active=True)
        Variant.objects.create(
            game=game,
            name="archived",
            active=False,
        )

        game_data = return_game_json(game)
        self.assertEqual(list(game_data["variant"].keys()), ["default"])


class GameListTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.waterloo = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.diplomacy = Game.objects.create(
            name="diplomacy",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "diplomacy",
            },
            active=True,
        )
        self.diplomacy_variant = Variant.objects.create(
            game=self.diplomacy,
            name="variant",
            max_players=7,
            max_watchers=15,
            game_json={
                "game": "diplomacy variant",
            },
            active=True,
        )


    def test_game_list_success_two_games(self):
        data = {
            "game_name_list": ['waterloo', 'diplomacy'],
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["game_list"]), 2)

    def test_game_list_success_two_games_and_unknown_games(self):
        data = {
            "game_name_list": ['waterloo', 'diplomacy', 'terra mystica'],
        }
        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["game_list"]), 2)

    def test_game_list_without_names_returns_active_games(self):
        self.diplomacy.active = False
        self.diplomacy.save()
        data = {
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(
            [game["name"] for game in response_content["game_list"]],
            ['waterloo'],
        )

    def test_game_list_rejects_a_non_list(self):
        data = {
            "game_name_list": "waterloo",
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 400)

    def test_game_list_empty_unknown_game(self):
        data = {
            "game_name_list": ['terra_mystica', 'diplomacy'],
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["game_list"]), 1)
        self.assertEqual(len(response_content["game_list"][0]["variant"]), 2)

    def test_game_list_failure_invalid_json(self):
        request = self.factory.post(reverse('game_list'), data="not a valid json", content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 400)

    def test_game_list_returns_inactive_game(self):
        self.diplomacy.active = False
        self.diplomacy.save()
        data = {
            "game_name_list": ['waterloo', 'diplomacy'],
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(
            sorted(game["name"] for game in response_content["game_list"]),
            ['diplomacy', 'waterloo'],
        )

    def test_game_list_rejects_get_request(self):
        request = self.factory.get(reverse('game_list'))
        response = game_list(request)
        self.assertEqual(response.status_code, 405)



class OptionsFieldTest(TestCase):
    def test_options_default_to_an_empty_block(self):
        game = Game.objects.create(name="waterloo")
        variant = Variant.objects.create(game=game, name="short")

        self.assertEqual(game.options, {})
        self.assertEqual(variant.options, {})

    def test_an_emptied_form_field_becomes_an_empty_block(self):
        game = Game(name="waterloo", game_json={"fixed": []}, options=None)

        game.full_clean()

        self.assertEqual(game.options, {})

    def test_starting_game_json_replaces_the_options_block(self):
        game = Game.objects.create(
            name="waterloo",
            game_json={"fixed": [], "options": {"fix_positions": None}},
            options={"screen_capture": False},
        )

        started = starting_game_json(game)

        self.assertEqual(started, {"fixed": [], "options": {"screen_capture": False}})
        # the game itself is left as it was
        self.assertEqual(game.game_json["options"], {"fix_positions": None})

    def test_starting_game_json_of_a_variant_uses_the_options_of_the_variant(self):
        game = Game.objects.create(name="waterloo", options={"screen_capture": False})
        variant = Variant.objects.create(game=game, name="short", game_json={"fixed": []})

        self.assertEqual(starting_game_json(variant), {"fixed": [], "options": {}})


class SyncGameJsonTest(TestCase):
    NEW_GAME = "11111111-2222-3333-4444-555555555555"
    NEW_VARIANT = "66666666-7777-8888-9999-000000000000"

    def setUp(self):
        self.game = Game.objects.create(name="waterloo", game_json={"fixed": []}, options={"a": 1})
        self.variant = Variant.objects.create(game=self.game, name="short", game_json={"fixed": [1]})

    def game_entry(self, **changes):
        return {
            "key": str(self.game.key),
            "name": "waterloo",
            "min_players": 0,
            "max_players": 2,
            "max_watchers": 10,
            "max_sessions": 10,
            "game_json": {"fixed": []},
            **changes,
        }

    def variant_entry(self, **changes):
        return {
            "key": str(self.variant.key),
            "game_key": str(self.game.key),
            "game_name": "waterloo",
            "name": "short",
            "min_players": 0,
            "max_players": 2,
            "max_watchers": 10,
            "game_json": {"fixed": [1]},
            **changes,
        }

    def document(self, **game_changes):
        return {"games": [self.game_entry(**game_changes)], "variants": [self.variant_entry()]}

    def sync(self, document, *args):
        output = io.StringIO()
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump(document, handle)
            handle.flush()
            call_command("sync_game_json", handle.name, *args, stdout=output)
        return output.getvalue()

    def test_identical_games_are_left_alone(self):
        before = Game.objects.get(pk=self.game.pk).updated_at

        output = self.sync(self.document())

        self.assertEqual(output.strip(), "0 change(s) applied")
        self.assertEqual(Game.objects.get(pk=self.game.pk).updated_at, before)

    def test_game_json_is_copied(self):
        output = self.sync(self.document(game_json={"fixed": [2]}))

        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": [2]})
        self.assertIn("game waterloo: game_json updated", output)
        self.assertIn("1 change(s) applied", output)

    def test_display_name_is_copied(self):
        document = self.document(display_name="Waterloo 1815")
        document["variants"][0]["display_name"] = "Short scenario"

        output = self.sync(document)

        self.game.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.game.display_name, "Waterloo 1815")
        self.assertEqual(self.variant.display_name, "Short scenario")
        self.assertIn("game waterloo: display_name updated", output)
        self.assertIn("2 change(s) applied", output)

    def test_game_json_and_display_name_make_one_change(self):
        output = self.sync(self.document(game_json={"fixed": [2]}, display_name="Waterloo 1815"))

        self.game.refresh_from_db()
        self.assertEqual((self.game.game_json, self.game.display_name), ({"fixed": [2]}, "Waterloo 1815"))
        self.assertIn("1 change(s) applied", output)

    def test_a_document_without_display_name_leaves_it_alone(self):
        Game.objects.filter(pk=self.game.pk).update(display_name="Waterloo 1815")

        output = self.sync(self.document())

        self.game.refresh_from_db()
        self.assertEqual(self.game.display_name, "Waterloo 1815")
        self.assertIn("0 change(s) applied", output)

    def test_unknown_game_is_created_with_its_display_name(self):
        document = self.document()
        document["games"].append(self.game_entry(key=self.NEW_GAME, name="alamo", display_name="The Alamo"))
        document["variants"].append(self.variant_entry(
            key=self.NEW_VARIANT, game_key=self.NEW_GAME, game_name="alamo", display_name="Night assault",
        ))

        self.sync(document)

        self.assertEqual(Game.objects.get(name="alamo").display_name, "The Alamo")
        self.assertEqual(Variant.objects.get(key=self.NEW_VARIANT).display_name, "Night assault")

    def test_nothing_else_is_copied_to_a_known_game(self):
        output = self.sync(self.document(max_players=9, options={"a": 2}))

        self.game.refresh_from_db()
        self.assertEqual(self.game.max_players, 2)
        # the options of this database are its own
        self.assertEqual(self.game.options, {"a": 1})
        self.assertIn("0 change(s) applied", output)

    def test_dry_run_writes_nothing(self):
        document = self.document(game_json={"fixed": [2]})
        document["games"].append(self.game_entry(key=self.NEW_GAME, name="alamo"))
        document["variants"].append(self.variant_entry(key=self.NEW_VARIANT, game_key=self.NEW_GAME, game_name="alamo"))

        output = self.sync(document, "--dry-run")

        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": []})
        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(Variant.objects.count(), 1)
        self.assertIn("game waterloo: game_json would change", output)
        self.assertIn("game alamo: would be created inactive", output)
        self.assertIn("variant alamo / short: would be created inactive", output)
        self.assertIn("3 change(s) to apply", output)

    def test_variant_game_json_is_copied(self):
        document = self.document()
        document["variants"][0]["game_json"] = {"fixed": [3]}

        self.sync(document)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.game_json, {"fixed": [3]})

    def test_unknown_game_is_created_inactive_with_empty_options(self):
        document = self.document()
        document["games"].append(self.game_entry(
            key=self.NEW_GAME, name="alamo", max_players=4, max_sessions=3,
            game_json={"fixed": [7]}, options={"a": 1}, active=True,
        ))
        document["variants"].append(self.variant_entry(
            key=self.NEW_VARIANT, game_key=self.NEW_GAME, game_name="alamo", name="night", options={"b": 1},
        ))

        output = self.sync(document)

        created = Game.objects.get(name="alamo")
        self.assertEqual(str(created.key), self.NEW_GAME)
        self.assertFalse(created.active)
        self.assertEqual(created.options, {})
        self.assertEqual(created.game_json, {"fixed": [7]})
        self.assertEqual((created.max_players, created.max_sessions), (4, 3))
        variant = Variant.objects.get(game=created)
        self.assertEqual((variant.name, variant.active, variant.options), ("night", False, {}))
        self.assertIn("game alamo: created inactive, with empty options", output)
        self.assertIn("2 change(s) applied", output)

    def test_a_name_taken_by_another_game_is_skipped(self):
        document = {"games": [self.game_entry(key=self.NEW_GAME, game_json={"fixed": [9]})], "variants": []}

        output = self.sync(document)

        self.assertIn("game waterloo: the name is taken here by another game, skipped", output)
        self.assertEqual(Game.objects.count(), 1)
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": []})

    def test_malformed_document_is_refused(self):
        for document in (
            [],
            {"games": []},
            {"games": [{"key": "x", "game_json": {}}], "variants": []},
            {"games": [self.game_entry(display_name=3)], "variants": []},
        ):
            with self.subTest(document=document):
                with self.assertRaises(CommandError):
                    self.sync(document)
