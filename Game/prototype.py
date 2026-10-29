"""
The game_json and the resources of a prototype, uploaded by its developers on
the proto/ pages (Game/proto_views.py).

The resources of a game live in settings.PROTOTYPES_DIR/<key of the game>/,
served by Raffaillac under settings.PROTOTYPES_URL + <key>/ (OBG/Prototypes,
next to OBG/Games, never synced by deploy.sh). An archive replaces the whole
folder at once; the variants of the game share it, each with its own game_json.
A prototype weighs settings.PROTOTYPE_MAX_SIZE at most: its unpacked resources
plus the game_json of the game and of each of its variants.

Before a game_json is stored, it is checked (check_game_json): Tourtoirac builds
it as it would build a session (kinds unknown or misplaced, duplicated ids,
components it cannot build), and every picture must answer on Raffaillac, where
the browsers will ask for it. The archive is therefore uploaded first.

The documents of a game or a variant (rules, charts...: Game.documents, never in
its game_json) are uploaded apart (read_documents_upload); their src follows
the rules of the images below, and each one must answer as well. A "documents"
block left in an uploaded game_json is moved to them.

In the game_json, an image (src, front_src, back_src, icon) is either a path
relative to the archive, which is written as the URL of the prototype, or an
absolute path under the folder of the prototype or under /Games/ (resources
shared by every game). Anything else is refused: another prototype, another
site, a path climbing out of its folder.
"""
import json
import shutil
import stat
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from django.conf import settings

from Game.models import Game, Variant
from Game.tools import read_documents, starting_game_json
from Session import manage_clients

# the keys of a game_json whose value is the URL of a resource
RESOURCE_KEYS = ("src", "front_src", "back_src", "icon")
# what an archive may hold. No SVG: served from the site itself, it could run
# scripts in its pages
ARCHIVE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".json", ".txt"}
SHARED_PREFIX = "/Games/"


class PrototypeError(Exception):
    """An upload refused: the message is for its developer."""


def prototypes_of(user):
    """The games a user develops; every prototype for a superuser."""
    games = Game.objects.all() if user.is_superuser else user.prototypes.all()
    if user.is_superuser:
        games = games.exclude(prototype_key="", prototype_users=None)
    return games.distinct().order_by("name")


def _megabytes(size: int) -> str:
    return f"{size / (1024 * 1024):.0f} Mo"


def json_size(game_json) -> int:
    return len(json.dumps(game_json, ensure_ascii=False).encode())


def stored_json_size(game: Game, replacing=None) -> int:
    """What the game_json and the documents of the game and of its variants weigh, but the game_json being replaced."""
    sources = [game, *game.variant_set.all()]
    return sum(json_size(source.documents) + (
        0 if type(source) is type(replacing) and source.pk == replacing.pk else json_size(source.game_json))
        for source in sources)


def folder_size(game: Game) -> int:
    folder = resources_dir(game)
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file()) if folder.is_dir() else 0


def source_of(game: Game, variant_name: str):
    """The game itself ("default"), or one of its variants."""
    if variant_name in ("", "default"):
        return game
    variant = game.variant_set.filter(name=variant_name).first()
    if variant is None:
        raise PrototypeError(f"Variante inconnue : {variant_name}")
    return variant


def resources_url(game: Game) -> str:
    return f"{settings.PROTOTYPES_URL}{game.key}/"


def resources_dir(game: Game) -> Path:
    return Path(settings.PROTOTYPES_DIR) / str(game.key)


def _clean_parts(path: str) -> list:
    """The parts of a relative path, refused when it climbs out of its folder."""
    parts = [part for part in PurePosixPath(path.replace("\\", "/")).parts if part not in ("", ".")]
    if not parts or ".." in parts or parts[0] == "/":
        raise PrototypeError(f"Chemin refusé : {path}")
    return parts


# -------------------------------------------------
# game_json
# -------------------------------------------------

def _resource(value: str, own_url: str) -> str:
    """The URL a resource of the game_json is stored with."""
    if value.startswith(SHARED_PREFIX) or value.startswith(own_url):
        prefix = SHARED_PREFIX if value.startswith(SHARED_PREFIX) else own_url
        _clean_parts(value[len(prefix):])
        return value
    if value.startswith("/") or ":" in value.split("/", 1)[0]:
        raise PrototypeError(
            f"Ressource refusée : {value} (relative à l'archive, ou sous {own_url} ou {SHARED_PREFIX})"
        )
    return own_url + "/".join(_clean_parts(value))


def _rewrite(node, own_url: str, used: list):
    if isinstance(node, dict):
        rewritten = {}
        for key, value in node.items():
            if key in RESOURCE_KEYS and isinstance(value, str) and value:
                value = _resource(value, own_url)
                used.append(value)
                rewritten[key] = value
            else:
                rewritten[key] = _rewrite(value, own_url, used)
        return rewritten
    if isinstance(node, list):
        return [_rewrite(value, own_url, used) for value in node]
    return node


def read_game_json(game: Game, raw: bytes, replacing: Game | Variant | None = None) -> tuple:
    """
    Reads an uploaded game_json and writes its resources as URLs of the prototype.
    :param replacing: the game or the variant whose game_json it replaces, not counted
        in the size of the prototype
    The deeper checks (ids of the components...) are Tourtoirac's, at the
    creation of a session: it refuses a broken game and names the culprit.
    :return: (game_json, URLs of every picture it shows, /Games/ ones included)
    """
    try:
        game_json = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as error:
        raise PrototypeError(f"JSON illisible : {error}") from error
    if not isinstance(game_json, dict):
        raise PrototypeError("Le game_json doit être un objet JSON.")
    for list_name in ("fixed", "movable", "dice"):
        if list_name in game_json and not isinstance(game_json[list_name], list):
            raise PrototypeError(f"« {list_name} » doit être une liste.")
    # the options of a game are set by the administrator (Game.options), never by its game_json
    game_json.pop("options", None)
    used = []
    own_url = resources_url(game)
    game_json = _rewrite(game_json, own_url, used)
    total = folder_size(game) + stored_json_size(game, replacing) + json_size(game_json)
    if total > settings.PROTOTYPE_MAX_SIZE:
        raise PrototypeError(
            f"Le prototype pèserait {_megabytes(total)}, plus que {_megabytes(settings.PROTOTYPE_MAX_SIZE)}."
        )
    return game_json, sorted(set(used))


def used_resources(game: Game) -> list:
    """The URLs of the prototype the stored game_json of the game and its variants use, read without any check."""
    own_url, used = resources_url(game), set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in RESOURCE_KEYS and isinstance(value, str) and value.startswith(own_url):
                    used.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for source in (game, *game.variant_set.all()):
        walk(source.game_json)
        walk(source.documents)
    return sorted(used)


def split_documents(game: Game, game_json: dict) -> list | None:
    """
    Takes the "documents" block out of a game_json read by read_game_json (its
    sources already written as URLs of the prototype).
    :return: the documents, or None when the game_json had no such block
    """
    if "documents" not in game_json:
        return None
    documents = game_json.pop("documents")
    if not isinstance(documents, list):
        raise PrototypeError("« documents » doit être une liste.")
    return read_documents(documents)


def read_documents_upload(game: Game, raw: str) -> list:
    """
    Reads the documents a developer gives for the game or one of its variants:
    a JSON list of {"src": ..., "name": ...}, empty for none. A src is written
    as the URL of the prototype, like the images of a game_json.
    """
    raw = raw.strip()
    if not raw:
        return []
    try:
        documents = json.loads(raw)
    except ValueError as error:
        raise PrototypeError(f"JSON illisible : {error}") from error
    if not isinstance(documents, list) or any(
        not isinstance(document, dict) or not isinstance(document.get("src"), str) or not document["src"]
        for document in documents
    ):
        raise PrototypeError('Les documents s\'écrivent [{"src": "rules/regles.pdf", "name": "Règles"}, ...].')
    own_url = resources_url(game)
    return [{**document, "src": _resource(document["src"], own_url)} for document in read_documents(documents)]


def check_documents(documents) -> None:
    """Refuses documents that Raffaillac does not serve."""
    unreachable = unreachable_images(document["src"] for document in documents)
    if unreachable:
        raise PrototypeError("document(s) injoignable(s) : " + " ; ".join(unreachable[:PROBLEMS_SHOWN]))


# the most problems told to the developer at once
PROBLEMS_SHOWN = 15


def _answers(url: str) -> bool:
    request = urllib.request.Request(
        settings.OBG_RESOURCES_URL.rstrip("/") + urllib.parse.quote(url, safe="/"), method="HEAD"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def unreachable_images(urls) -> list:
    """The pictures that Raffaillac does not serve, as a browser would ask for them."""
    urls = sorted(set(urls))
    with ThreadPoolExecutor(max_workers=16) as pool:
        return [url for url, ok in zip(urls, pool.map(_answers, urls)) if not ok]


def check_game_json(source: Game | Variant, game_json: dict, images) -> None:
    """
    Refuses a game_json that would not be played as written: Tourtoirac builds it
    with the options of its game or variant, and every picture must answer.
    :param images: every picture the game_json shows, /Games/ ones included
    """
    candidate = starting_game_json(source)
    candidate.update(game_json)
    candidate["options"] = starting_game_json(source)["options"]
    try:
        problems = manage_clients.tourtoirac("POST", "/admin/check", {"game_json": candidate}).get("problems", [])
    except manage_clients.ServiceUnavailable as error:
        raise PrototypeError(f"Impossible de vérifier le jeu : Tourtoirac ne répond pas ({error}).") from error
    problems = [str(problem) for problem in problems]
    unreachable = unreachable_images(images)
    problems += [f"image injoignable : {url}" for url in unreachable]
    if problems:
        shown = problems[:PROBLEMS_SHOWN]
        more = f" … et {len(problems) - len(shown)} autre(s)" if len(problems) > len(shown) else ""
        raise PrototypeError(
            f"game_json refusé, {len(problems)} problème(s) : " + " ; ".join(shown) + more
        )


def missing_resources(game: Game, urls) -> list:
    """The URLs of the prototype that no file of its folder answers."""
    own_url, folder = resources_url(game), resources_dir(game)
    return [url for url in urls if not (folder / url[len(own_url):]).is_file()]


# -------------------------------------------------
# Archive of the resources
# -------------------------------------------------

def _members(archive: zipfile.ZipFile) -> list:
    """The files of the archive with where they go, every one checked first."""
    files = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            raise PrototypeError(f"Lien symbolique refusé : {info.filename}")
        parts = _clean_parts(info.filename)
        # what the Mac adds to its archives
        if parts[0] == "__MACOSX" or parts[-1].startswith("._") or parts[-1] == ".DS_Store":
            continue
        if PurePosixPath(parts[-1]).suffix.lower() not in ARCHIVE_SUFFIXES:
            raise PrototypeError(
                f"Type de fichier refusé : {info.filename} (acceptés : {', '.join(sorted(ARCHIVE_SUFFIXES))})"
            )
        files.append((info, parts))
    if not files:
        raise PrototypeError("L'archive ne contient aucun fichier.")
    if len(files) > settings.PROTOTYPE_FILES_MAX:
        raise PrototypeError(f"Plus de {settings.PROTOTYPE_FILES_MAX} fichiers dans l'archive.")
    # an archive of a folder: its content is the root of the prototype
    tops = {parts[0] for _, parts in files}
    if len(tops) == 1 and all(len(parts) > 1 for _, parts in files):
        files = [(info, parts[1:]) for info, parts in files]
    return files


def install_archive(game: Game, upload) -> int:
    """
    Unpacks a zip archive of resources in place of the folder of the prototype.
    :param upload: the uploaded file (read as a stream, never trusted for its sizes)
    :return: the number of files installed
    """
    # what the game_json of the game and of its variants leave to the resources
    budget = settings.PROTOTYPE_MAX_SIZE - stored_json_size(game)
    if upload.size > budget:
        raise PrototypeError(f"Archive de plus de {_megabytes(budget)}, la place qui reste au prototype.")
    try:
        archive = zipfile.ZipFile(upload)
    except zipfile.BadZipFile as error:
        raise PrototypeError("Ce fichier n'est pas une archive zip.") from error

    root = Path(settings.PROTOTYPES_DIR)
    root.mkdir(parents=True, exist_ok=True)
    target = resources_dir(game)
    staging = root / f".upload-{uuid.uuid4().hex}"
    try:
        with archive:
            files = _members(archive)
            for info, parts in files:
                destination = staging.joinpath(*parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                # the sizes the archive declares may lie: the bytes are counted
                with archive.open(info) as source, open(destination, "wb") as out:
                    while chunk := source.read(1024 * 1024):
                        budget -= len(chunk)
                        if budget < 0:
                            raise PrototypeError(
                                f"L'archive décompressée dépasse {_megabytes(settings.PROTOTYPE_MAX_SIZE - stored_json_size(game))}, "
                                f"la place qui reste au prototype."
                            )
                        out.write(chunk)
        # the new folder takes the place of the old one in one move each
        retired = root / f".old-{uuid.uuid4().hex}"
        if target.exists():
            target.rename(retired)
        staging.rename(target)
        shutil.rmtree(retired, ignore_errors=True)
    except (zipfile.BadZipFile, RuntimeError, OSError) as error:
        # RuntimeError: an encrypted member
        raise PrototypeError(f"Archive illisible : {error}") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return len(files)


def folder_summary(game: Game) -> dict:
    """How many files the prototype has, their size, when they were installed, and its total weight."""
    folder = resources_dir(game)
    files = [path for path in folder.rglob("*") if path.is_file()] if folder.is_dir() else []
    size = sum(path.stat().st_size for path in files)
    return {
        "files": len(files),
        "size": size,
        "installed_at": folder.stat().st_mtime if files else None,
        "total": size + stored_json_size(game),
        "max": settings.PROTOTYPE_MAX_SIZE,
    }
