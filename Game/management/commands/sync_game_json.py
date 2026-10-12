import json
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Game.models import Game, Variant

# what a game or a variant created here takes from the document, besides its
# key and its game_json
GAME_FIELDS = ("name", "min_players", "max_players", "max_watchers", "max_sessions")
VARIANT_FIELDS = ("name", "min_players", "max_players", "max_watchers")


class Command(BaseCommand):
    help = (
        "Copy the game_json of the games and variants described by a JSON "
        "document (standard input, or a file) into this database. Rows are "
        "matched by key. A game or a variant unknown here is created inactive, "
        "with empty options. Options are never copied, nothing is deleted and "
        "sessions are not touched."
    )

    def add_arguments(self, parser):
        parser.add_argument("source", nargs="?", default="-", help="JSON file, or - for standard input.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change, without writing.",
        )

    def handle(self, *args, **options):
        document = self.read(options["source"])
        self.dry_run = options["dry_run"]
        # keys of the games a dry run would have created: their variants follow
        self.planned_games = set()
        changes = 0
        with transaction.atomic():
            for entry in document["games"]:
                changes += self.sync_game(entry)
            for entry in document["variants"]:
                changes += self.sync_variant(entry)
        verb = "to apply" if self.dry_run else "applied"
        self.stdout.write(f"{changes} change(s) {verb}")

    def read(self, source):
        try:
            if source == "-":
                document = json.load(sys.stdin)
            else:
                with open(source, encoding="utf-8") as handle:
                    document = json.load(handle)
        except (OSError, ValueError) as error:
            raise CommandError(f"Cannot read the games to synchronise: {error}") from error
        if (
            not isinstance(document, dict)
            or not isinstance(document.get("games"), list)
            or not isinstance(document.get("variants"), list)
        ):
            raise CommandError('Expected {"games": [...], "variants": [...]}.')
        for entries, fields in ((document["games"], GAME_FIELDS), (document["variants"], VARIANT_FIELDS + ("game_key",))):
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or not entry.get("key")
                    or not isinstance(entry.get("game_json"), dict)
                    or any(entry.get(field) is None for field in fields)
                ):
                    raise CommandError(
                        f"Every entry needs a key, a game_json object and: {', '.join(fields)}."
                    )
        return document

    def update(self, label, row, entry) -> int:
        if row.game_json == entry["game_json"]:
            return 0
        self.stdout.write(f"{label}: game_json {'would change' if self.dry_run else 'updated'}")
        if not self.dry_run:
            row.game_json = entry["game_json"]
            row.save(update_fields=["game_json", "updated_at"])
        return 1

    def created(self, label) -> int:
        self.stdout.write(f"{label}: {'would be created' if self.dry_run else 'created'} inactive, with empty options")
        return 1

    def sync_game(self, entry) -> int:
        label = f"game {entry['name']}"
        game = Game.objects.filter(key=entry["key"]).first()
        if game is not None:
            return self.update(label, game, entry)
        if Game.objects.filter(name=entry["name"]).exists():
            # names are unique: this is another game, not ours to overwrite
            self.stdout.write(self.style.WARNING(f"{label}: the name is taken here by another game, skipped"))
            return 0
        self.planned_games.add(str(entry["key"]))
        if not self.dry_run:
            Game.objects.create(
                key=entry["key"],
                game_json=entry["game_json"],
                options={},
                active=False,
                **{field: entry[field] for field in GAME_FIELDS},
            )
        return self.created(label)

    def sync_variant(self, entry) -> int:
        label = f"variant {entry.get('game_name', entry['game_key'])} / {entry['name']}"
        variant = Variant.objects.filter(key=entry["key"]).first()
        if variant is not None:
            return self.update(label, variant, entry)
        game = Game.objects.filter(key=entry["game_key"]).first()
        if game is None:
            if self.dry_run and str(entry["game_key"]) in self.planned_games:
                return self.created(label)
            self.stdout.write(self.style.WARNING(f"{label}: its game is unknown here, skipped"))
            return 0
        if not self.dry_run:
            Variant.objects.create(
                key=entry["key"],
                game=game,
                game_json=entry["game_json"],
                options={},
                active=False,
                **{field: entry[field] for field in VARIANT_FIELDS},
            )
        return self.created(label)
