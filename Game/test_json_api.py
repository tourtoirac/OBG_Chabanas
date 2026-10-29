import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from Game.models import Game, Variant
from Session.models import Session


@override_settings(OBG_ADMIN_SECRET="test-maintenance-secret")
class GameJsonApiTest(TestCase):
    def setUp(self):
        self.game = Game.objects.create(
            name="Jeux_et_Strategies", active=False,
            game_json={"fixed": [], "movable": []}, options={"fix_positions": True},
        )
        self.variant = Variant.objects.create(
            game=self.game, name="aboukir", active=False,
            game_json={"movable": [{"id": "ship"}]}, options={"nationalities": ["France"]},
        )
        self.selector = {"game_name": self.game.name, "variant_name": self.variant.name}

    def post(self, route, data, secret="test-maintenance-secret"):
        return self.client.post(
            reverse(route), json.dumps(data), content_type="application/json",
            headers={"X-OBG-Admin-Secret": secret},
        )

    def replacement(self, selector=None, **fields):
        selector = selector or self.selector
        current = self.post("game_json_get", selector).json()
        return {**selector, "game_json": {"fixed": [], "movable": []},
                "expected_updated_at": current["updated_at"], **fields}

    def test_reads_the_base_game_without_a_variant(self):
        response = self.post("game_json_get", {"game_name": self.game.name})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "key": str(self.game.key), "game_name": self.game.name,
            "variant_name": "default", "game_json": self.game.game_json,
            "documents": [], "updated_at": self.game.updated_at.isoformat(),
        })

    def test_reads_an_inactive_variant_without_inheriting_the_base_json(self):
        response = self.post("game_json_get", self.selector)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game_json"], self.variant.game_json)
        self.assertEqual(response.json()["key"], str(self.variant.key))

    def test_both_routes_reject_missing_or_incorrect_credentials(self):
        for route in ("game_json_get", "game_json_update"):
            for secret in ("", "wrong"):
                with self.subTest(route=route, secret=secret):
                    self.assertEqual(self.post(route, self.selector, secret=secret).status_code, 403)

    @override_settings(OBG_ADMIN_SECRET="")
    def test_unconfigured_api_is_disabled_even_with_an_empty_header(self):
        for route in ("game_json_get", "game_json_update"):
            self.assertEqual(self.post(route, self.selector, secret="").status_code, 503)

    def test_only_post_is_accepted(self):
        for route in ("game_json_get", "game_json_update"):
            self.assertEqual(self.client.get(reverse(route)).status_code, 405)

    def test_authentication_happens_before_body_parsing(self):
        response = self.client.post(reverse("game_json_update"), "bad json",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_invalid_json_or_non_object_bodies_are_rejected(self):
        for body in ("{", "[]", "null", '"text"'):
            response = self.client.post(
                reverse("game_json_get"), body, content_type="application/json",
                headers={"X-OBG-Admin-Secret": "test-maintenance-secret"},
            )
            self.assertEqual(response.status_code, 400)

    def test_invalid_selectors_are_rejected(self):
        for selector in ({}, {"game_name": None}, {"game_name": []}, {"game_name": " "},
                         {"game_name": "x" * 65}, {**self.selector, "variant_name": 3},
                         {**self.selector, "variant_name": ""}):
            with self.subTest(selector=selector):
                self.assertEqual(self.post("game_json_get", selector).status_code, 400)

    def test_unknown_games_and_variants_return_404_without_creating_rows(self):
        for selector in ({"game_name": "absent"}, {**self.selector, "variant_name": "absent"}):
            self.assertEqual(self.post("game_json_get", selector).status_code, 404)
            self.assertEqual(self.post("game_json_update", {
                **selector, "game_json": {}, "expected_updated_at": "revision",
            }).status_code, 404)
        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(Variant.objects.count(), 1)

    def test_update_requires_an_object_and_a_revision(self):
        payload = self.replacement()
        invalid = [self.selector, {**self.selector, "game_json": {}},
                   {**payload, "expected_updated_at": None},
                   {**payload, "expected_updated_at": ""}]
        invalid += [{**payload, "game_json": value} for value in (None, [], "text", True)]
        for body in invalid:
            with self.subTest(body=body):
                self.assertEqual(self.post("game_json_update", body).status_code, 400)

    def test_replaces_variant_json_without_changing_metadata_or_sessions(self):
        session = Session.objects.create(game=self.game, variant_name="aboukir", game_json={"old": True})
        old_base = self.game.game_json
        payload = self.replacement(game_json={"movable": [{"id": "ship", "rotation_step": 60}]},
                                   options={}, active=True, min_players=99)
        response = self.post("game_json_update", payload)
        self.assertEqual(response.status_code, 200)
        self.variant.refresh_from_db()
        self.game.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(self.variant.game_json, payload["game_json"])
        self.assertNotEqual(response.json()["updated_at"], payload["expected_updated_at"])
        self.assertEqual(self.variant.options, {"nationalities": ["France"]})
        self.assertFalse(self.variant.active)
        self.assertEqual(self.variant.min_players, 0)
        self.assertEqual(self.game.game_json, old_base)
        self.assertEqual(session.game_json, {"old": True})

    def test_default_selector_updates_the_game_only(self):
        payload = self.replacement({"game_name": self.game.name, "variant_name": "default"},
                                   game_json={"fixed": []})
        self.assertEqual(self.post("game_json_update", payload).status_code, 200)
        self.game.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": []})
        self.assertEqual(self.variant.game_json, {"movable": [{"id": "ship"}]})

    def test_stale_revision_cannot_overwrite_a_newer_edit(self):
        payload = self.replacement()
        self.assertEqual(self.post("game_json_update", payload).status_code, 200)
        self.assertEqual(self.post("game_json_update", {**payload, "game_json": {}}).status_code, 409)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.game_json, payload["game_json"])

    def test_empty_object_is_a_valid_replacement(self):
        self.assertEqual(self.post("game_json_update", self.replacement(game_json={})).status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.game_json, {})

    def test_identical_replacement_keeps_the_revision(self):
        payload = self.replacement(game_json=self.variant.game_json)
        response = self.post("game_json_update", payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated_at"], payload["expected_updated_at"])

    def test_the_documents_change_only_when_the_request_carries_them(self):
        rules = [{"src": "/Games/x/rules.pdf", "name": "Règles"}]
        self.assertEqual(self.post("game_json_update", self.replacement(documents=rules)).status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.documents, rules)
        self.assertEqual(self.post("game_json_update", self.replacement()).status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.documents, rules)
        for wrong in ({"src": "/a.pdf"}, [{"name": "no src"}]):
            with self.subTest(documents=wrong):
                self.assertEqual(self.post("game_json_update", self.replacement(documents=wrong)).status_code, 400)

    def test_header_authentication_works_without_browser_csrf_tokens(self):
        self.client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("game_json_update", self.replacement()).status_code, 200)
