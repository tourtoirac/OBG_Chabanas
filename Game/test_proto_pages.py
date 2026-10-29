import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from Game.models import Game, Variant
from Game.prototype import PrototypeError, read_game_json


def zip_of(files: dict, symlink: str | None = None) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = 0o120777 << 16
            archive.writestr(info, "/etc/passwd")
    return SimpleUploadedFile("resources.zip", buffer.getvalue(), content_type="application/zip")


class ProtoPagesTests(TestCase):
    """The developers of a prototype upload its game_json, its variants' and its resources."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.settings_override = override_settings(PROTOTYPES_DIR=Path(self.folder))
        self.settings_override.enable()
        # Tourtoirac and Raffaillac are not there: every check passes unless a test says otherwise
        self.problems = []
        self.unreachable = set()
        for target, effect in (
            ("Game.prototype.manage_clients.tourtoirac", lambda *args: {"problems": self.problems}),
            ("Game.prototype._answers", lambda url: url not in self.unreachable),
        ):
            patcher = patch(target, side_effect=effect)
            self.mocks = getattr(self, "mocks", []) + [patcher.start()]
            self.addCleanup(patcher.stop)
        self.dev = User.objects.create_user("dev", password="x")
        self.other = User.objects.create_user("other", password="x")
        self.game = Game.objects.create(name="proto", prototype_key="k", options={"fix_positions": True})
        self.game.prototype_users.add(self.dev)
        self.variant = Variant.objects.create(game=self.game, name="solo")
        self.foreign = Game.objects.create(name="foreign", prototype_key="k2")
        self.foreign.prototype_users.add(self.other)
        self.client.force_login(self.dev)

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.folder, ignore_errors=True)

    def url(self, name, game=None):
        return reverse(name, args=[(game or self.game).key])

    def upload_json(self, game_json, variant="default", game=None):
        upload = SimpleUploadedFile("game.json", json.dumps(game_json).encode(), content_type="application/json")
        return self.client.post(self.url("proto_game_json", game), {"game_json": upload, "variant": variant})

    def own(self, path):
        return f"/Prototypes/{self.game.key}/{path}"

    # -------------------------------------------------

    def test_login_is_required(self):
        self.client.logout()
        response = self.client.get(reverse("proto_home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("proto_login"), response["Location"])

    def test_a_user_sees_and_changes_only_their_prototypes(self):
        page = self.client.get(reverse("proto_home")).content.decode()
        self.assertIn("proto", page)
        self.assertNotIn("foreign", page)
        self.assertEqual(self.upload_json({"fixed": []}, game=self.foreign).status_code, 404)
        self.assertEqual(self.client.post(self.url("proto_key", self.foreign), {"prototype_key": "x"}).status_code, 404)
        self.assertEqual(self.client.get(self.url("proto_game_json_download", self.foreign)).status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.prototype_key, "k2")

    def test_the_game_json_resources_become_urls_of_the_prototype(self):
        self.upload_json({
            "fixed": [{"id": "map", "src": "boards/map.jpg"}],
            "movable": [{"id": "t", "front_src": "./tokens\\a.png", "back_src": "/Games/Common/back.png",
                         "icon": self.own("icons/i.png")}],
            "options": {"fix_positions": False},
        })
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json["fixed"][0]["src"], self.own("boards/map.jpg"))
        token = self.game.game_json["movable"][0]
        self.assertEqual(token["front_src"], self.own("tokens/a.png"))
        self.assertEqual(token["back_src"], "/Games/Common/back.png")
        # the options stay the administrator's
        self.assertNotIn("options", self.game.game_json)
        self.assertEqual(self.game.options, {"fix_positions": True})

    def test_resources_out_of_the_prototype_are_refused(self):
        for src in ("../x.png", "/etc/passwd", "https://evil.example/x.png", "//evil.example/x.png",
                    f"/Prototypes/{self.foreign.key}/x.png", "/Games/../Prototypes/x.png", "javascript:alert(1)"):
            with self.subTest(src=src), self.assertRaises(PrototypeError):
                read_game_json(self.game, json.dumps({"fixed": [{"id": "a", "src": src}]}).encode())

    def test_a_bad_game_json_changes_nothing(self):
        self.game.game_json = {"fixed": []}
        self.game.save()
        for raw in (b"not json", b"[1, 2]", b'{"fixed": {}}'):
            upload = SimpleUploadedFile("game.json", raw)
            self.client.post(self.url("proto_game_json"), {"game_json": upload, "variant": "default"})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": []})

    def test_a_variant_has_its_own_game_json(self):
        self.upload_json({"fixed": [{"id": "map", "src": "solo.jpg"}]}, variant="solo")
        self.variant.refresh_from_db()
        self.game.refresh_from_db()
        self.assertEqual(self.variant.game_json["fixed"][0]["src"], self.own("solo.jpg"))
        self.assertEqual(self.game.game_json, {})
        response = self.client.get(self.url("proto_game_json_download") + "?variant=solo")
        self.assertEqual(json.loads(response.content), self.variant.game_json)
        self.assertEqual(self.upload_json({}, variant="unknown").status_code, 302)

    def test_the_archive_replaces_the_resources(self):
        folder = Path(self.folder) / str(self.game.key)
        self.client.post(self.url("proto_archive"), {"archive": zip_of({"proto/a.png": b"1", "proto/b/c.jpg": b"2"})})
        self.assertEqual(sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()),
                         ["a.png", "b/c.jpg"])
        self.client.post(self.url("proto_archive"), {"archive": zip_of({"d.png": b"3", "__MACOSX/._d.png": b""})})
        self.assertEqual([p.name for p in folder.rglob("*") if p.is_file()], ["d.png"])

    def test_a_dangerous_archive_changes_nothing(self):
        folder = Path(self.folder) / str(self.game.key)
        self.client.post(self.url("proto_archive"), {"archive": zip_of({"a.png": b"1"})})
        for archive in (zip_of({"../escape.png": b"x"}), zip_of({"x.svg": b"<svg/>"}), zip_of({"x.html": b"<p>"}),
                        zip_of({"a.png": b"1"}, symlink="link.png"),
                        SimpleUploadedFile("r.zip", b"not a zip")):
            self.client.post(self.url("proto_archive"), {"archive": archive})
        self.assertEqual([p.name for p in folder.rglob("*") if p.is_file()], ["a.png"])
        self.assertFalse((Path(self.folder) / "escape.png").exists())
        self.assertEqual([p.name for p in Path(self.folder).iterdir()], [str(self.game.key)])

    def test_the_prototype_weighs_at_most_its_maximum(self):
        with override_settings(PROTOTYPE_MAX_SIZE=1000):
            # unpacked size counted from the bytes, whatever the archive declares
            response = self.client.post(self.url("proto_archive"), {"archive": zip_of({"big.png": b"0" * 2000})})
            self.assertFalse((Path(self.folder) / str(self.game.key)).exists())
            self.client.post(self.url("proto_archive"), {"archive": zip_of({"a.png": b"0" * 600})})
            # the game_json of the game and of its variants count too
            self.upload_json({"fixed": [{"id": "x" * 300}]}, variant="solo")
            self.upload_json({"fixed": [{"id": "y" * 300}]})
            self.variant.refresh_from_db()
            self.game.refresh_from_db()
            self.assertIn("x" * 300, json.dumps(self.variant.game_json))
            self.assertEqual(self.game.game_json, {})
        self.assertEqual(response.status_code, 302)

    def test_the_key_can_be_changed_but_not_emptied(self):
        self.client.post(self.url("proto_key"), {"prototype_key": " new "})
        self.game.refresh_from_db()
        self.assertEqual(self.game.prototype_key, "new")
        self.client.post(self.url("proto_key"), {"prototype_key": " "})
        self.game.refresh_from_db()
        self.assertEqual(self.game.prototype_key, "new")

    def test_the_page_tells_what_the_archive_misses(self):
        self.upload_json({"fixed": [{"id": "map", "src": "boards/map.jpg"}]})
        page = self.client.get(reverse("proto_home")).content.decode()
        self.assertIn(self.own("boards/map.jpg"), page)

    def test_the_engine_refuses_a_broken_game(self):
        self.problems = ["list \"fixed\": component 'x' has kind 'bord', unknown here"]
        self.upload_json({"fixed": [{"kind": "bord", "id": "x"}]})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {})
        page = self.client.get(reverse("proto_home")).content.decode()
        self.assertIn("unknown here", page)

    def test_the_engine_checks_the_game_with_its_options(self):
        self.upload_json({"fixed": [{"kind": "board", "id": "map", "src": "map.jpg"}]})
        tourtoirac = self.mocks[0]
        method, path, body = tourtoirac.call_args.args
        self.assertEqual((method, path), ("POST", "/admin/check"))
        self.assertEqual(body["game_json"]["options"], {"fix_positions": True})
        self.assertEqual(body["game_json"]["fixed"][0]["src"], self.own("map.jpg"))

    def test_every_picture_must_answer(self):
        self.unreachable = {self.own("map.jpg"), "/Games/Common/missing.png"}
        self.upload_json({"fixed": [{"kind": "board", "id": "map", "src": "map.jpg"}],
                          "movable": [{"kind": "token", "id": "t", "front_src": "/Games/Common/missing.png",
                                       "back_src": "/Games/Common/ok.png"}]})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {})
        page = self.client.get(reverse("proto_home")).content.decode()
        self.assertIn("image injoignable : /Games/Common/missing.png", page)
        self.assertNotIn("ok.png", page)

    def test_tourtoirac_down_stores_nothing(self):
        from Session.manage_clients import ServiceUnavailable
        self.mocks[0].side_effect = ServiceUnavailable("down")
        self.upload_json({"fixed": []})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {})

    def documents(self, documents, variant="default"):
        text = documents if isinstance(documents, str) else json.dumps(documents)
        return self.client.post(self.url("proto_documents"), {"documents": text, "variant": variant})

    def test_the_documents_are_declared_apart_from_the_game_json(self):
        self.documents([{"src": "rules/regles.pdf", "name": "Règles"}, {"src": "/Games/Common/aide.pdf"}])
        self.game.refresh_from_db()
        self.assertEqual(self.game.documents, [
            {"src": self.own("rules/regles.pdf"), "name": "Règles"},
            {"src": "/Games/Common/aide.pdf", "name": "/Games/Common/aide.pdf"},
        ])
        self.assertEqual(self.game.game_json, {})
        page = self.client.get(reverse("proto_home")).content.decode()
        self.assertIn("Règles", page)
        # a variant has its own; an empty text removes them
        self.documents([{"src": "solo.pdf", "name": "Solo"}], variant="solo")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.documents, [{"src": self.own("solo.pdf"), "name": "Solo"}])
        self.documents("", variant="solo")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.documents, [])

    def test_bad_documents_change_nothing(self):
        self.game.documents = [{"src": self.own("a.pdf"), "name": "A"}]
        self.game.save()
        self.unreachable = {self.own("missing.pdf")}
        for wrong in ("not json", '{"src": "a.pdf"}', '[{"name": "x"}]', [{"src": "../x.pdf"}],
                      [{"src": "https://evil.example/x.pdf"}], [{"src": "missing.pdf"}]):
            with self.subTest(documents=wrong):
                self.documents(wrong)
                self.game.refresh_from_db()
                self.assertEqual(self.game.documents, [{"src": self.own("a.pdf"), "name": "A"}])
        self.assertEqual(self.client.post(self.url("proto_documents", self.foreign), {"documents": ""}).status_code, 404)

    def test_a_documents_block_of_a_game_json_moves_to_the_documents(self):
        self.upload_json({"fixed": [], "documents": [{"src": "rules.pdf", "name": "Règles"}]})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": []})
        self.assertEqual(self.game.documents, [{"src": self.own("rules.pdf"), "name": "Règles"}])
        self.assertNotIn("documents", self.mocks[0].call_args.args[2]["game_json"])
        # a game_json without the block keeps the documents
        self.upload_json({"fixed": []})
        self.game.refresh_from_db()
        self.assertEqual(len(self.game.documents), 1)
        # an unreachable document is refused with the game_json
        self.unreachable = {self.own("gone.pdf")}
        self.upload_json({"fixed": [1], "documents": [{"src": "gone.pdf"}]})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json, {"fixed": []})
