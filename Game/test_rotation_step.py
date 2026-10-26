"""Data migration scope and preservation, using historical-model doubles."""
from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace
from unittest import TestCase


class RotationStepMigrationTest(TestCase):
    def apply_migration(self, documents):
        rows = [SimpleNamespace(game_json=deepcopy(doc), saves=[]) for doc in documents]
        for row in rows:
            row.save = lambda _row=row, **kwargs: _row.saves.append(kwargs)

        class Manager:
            def using(self, alias):
                self.alias = alias
                return self

            def all(self):
                return self

            def iterator(self):
                return iter(rows)

        models = {name: SimpleNamespace(objects=Manager()) for name in ("Game", "Variant")}
        calls = []

        def get_model(app, name):
            calls.append((app, name))
            return models[name]

        migration = import_module("Game.migrations.0008_token_rotation_step")
        migration.add_rotation_steps(SimpleNamespace(get_model=get_model),
                                    SimpleNamespace(connection=SimpleNamespace(alias="test_db")))
        self.assertEqual(calls, [("Game", "Game"), ("Game", "Variant")])
        return rows

    def test_only_missing_steps_on_rotatable_pieces_are_filled(self):
        pieces = [
            {"kind": "token", "orientable": True},
            {"kind": "card", "orientable": True},
            {"kind": "token", "orientable": True, "rotation_step": 60},
            {"kind": "token", "orientable": False},
            {"kind": "token", "orientable": "true"},
            {"kind": "board", "orientable": True},
        ]
        (row,) = self.apply_migration([{"movable": pieces}])
        result = row.game_json["movable"]
        self.assertEqual([p.get("rotation_step") for p in result], [45, 45, 60, None, None, None])
        self.assertTrue(all(save["using"] == "test_db" for save in row.saves))

    def test_containers_are_not_traversed_and_unchanged_rows_are_not_saved(self):
        doc = {"fixed": [{"kind": "bag", "components": [{"kind": "token", "orientable": True}]}]}
        (row,) = self.apply_migration([doc])
        self.assertEqual(row.game_json, doc)
        self.assertEqual(row.saves, [])

    def test_malformed_documents_are_ignored(self):
        rows = self.apply_migration([None, [], {}, {"movable": None}, {"dice": [None, 5]}])
        self.assertTrue(all(not row.saves for row in rows))
