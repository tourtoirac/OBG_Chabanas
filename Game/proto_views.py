"""
The pages of the developers of prototypes (proto/): an OBG user (a Django user,
staff or not) logs in, sees the prototypes they are attached to (Game.prototype_users,
set in the Django admin) and uploads their game_json, the archive of their
resources and their key. Every rule of the uploads is in Game/prototype.py.
"""
import json
import logging
from datetime import UTC, datetime

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from Game.models import Game
from Game.prototype import (
    PrototypeError,
    check_documents,
    check_game_json,
    folder_summary,
    install_archive,
    missing_resources,
    prototypes_of,
    read_documents_upload,
    read_game_json,
    resources_url,
    source_of,
    split_documents,
    used_resources,
)

logger = logging.getLogger(__name__)

LOGIN_URL = reverse_lazy("proto_login")
# the longest game_json a developer uploads
GAME_JSON_MAX = 10 * 1024 * 1024


class ProtoLoginView(auth_views.LoginView):
    template_name = "Game/proto_login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("proto_home")


class ProtoLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("proto_login")


def _documents_text(source) -> str:
    return json.dumps(source.documents, indent=2, ensure_ascii=False) if source.documents else ""


def _prototype(request, key) -> Game:
    """A game the user develops; any other is unknown to them."""
    game = prototypes_of(request.user).filter(key=key).first()
    if game is None:
        raise Http404("Prototype inconnu")
    return game


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def proto_home(request) -> HttpResponse:
    """The prototypes of the user, with their resources and what their game_json misses."""
    rows = []
    for game in prototypes_of(request.user).prefetch_related("prototype_users", "variant_set"):
        summary = folder_summary(game)
        if summary["installed_at"]:
            summary["installed_at"] = datetime.fromtimestamp(summary["installed_at"], UTC)
        used = used_resources(game)
        rows.append({
            "game": game,
            "url": resources_url(game),
            "summary": summary,
            "missing": missing_resources(game, used),
            "developers": ", ".join(user.username for user in game.prototype_users.all()),
            "variants": sorted(game.variant_set.all(), key=lambda variant: variant.name),
        })
    for row in rows:
        # the documents of the game and of each variant, as the developer edits them
        row["documents"] = [
            {"variant": "default", "label": "du jeu", "text": _documents_text(row["game"])},
            *({"variant": variant.name, "label": f"de la variante {variant.name}", "text": _documents_text(variant)}
              for variant in row["variants"]),
        ]
    return render(request, "Game/proto.html", {"rows": rows})


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def proto_game_json_download(request, key) -> HttpResponse:
    """The game_json of the prototype (?variant=: of one of its variants), to be edited and uploaded again."""
    game = _prototype(request, key)
    try:
        source = source_of(game, request.GET.get("variant", "default"))
    except PrototypeError as error:
        raise Http404(str(error)) from error
    filename = game.name if source is game else f"{game.name}-{source.name}"
    response = HttpResponse(json.dumps(source.game_json, indent=2, ensure_ascii=False),
                            content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.json"'
    return response


@login_required(login_url=LOGIN_URL)
@require_http_methods(["POST"])
def proto_game_json(request, key) -> HttpResponse:
    """
    Replaces the game_json of the prototype, or of one of its variants (field
    "variant", "default" for the game itself); the sessions already created keep theirs.
    """
    game = _prototype(request, key)
    upload = request.FILES.get("game_json")
    label = game.name
    try:
        source = source_of(game, request.POST.get("variant", "default"))
        if source is not game:
            label = f"{game.name} / {source.name}"
        if upload is None:
            raise PrototypeError("Aucun fichier envoyé.")
        if upload.size > GAME_JSON_MAX:
            raise PrototypeError(f"game_json de plus de {GAME_JSON_MAX // (1024 * 1024)} Mo.")
        game_json, images = read_game_json(game, upload.read(), replacing=source)
        # the documents live apart from the game_json: a block left in it moves to them
        documents = split_documents(game, game_json)
        # nothing is stored before the engine built it and every picture answered
        check_game_json(source, game_json, images)
    except PrototypeError as error:
        messages.error(request, f"{label} : {error}")
        return redirect("proto_home")
    source.game_json = game_json
    fields = ["game_json", "updated_at"]
    moved = ""
    if documents is not None:
        source.documents = documents
        fields.append("documents")
        moved = f" Son bloc « documents » ({len(documents)}) a été déplacé dans les documents."
    source.save(update_fields=fields)
    logger.info("game_json of prototype %s uploaded by %s", label, request.user)
    messages.success(request, f"{label} : game_json vérifié et enregistré ({len(images)} images).{moved}")
    return redirect("proto_home")


@login_required(login_url=LOGIN_URL)
@require_http_methods(["POST"])
def proto_documents(request, key) -> HttpResponse:
    """
    Replaces the documents of the prototype, or of one of its variants (field
    "variant"): the lobby lists those of the game, a session gets those of its
    game or variant when it is created.
    """
    game = _prototype(request, key)
    label = game.name
    try:
        source = source_of(game, request.POST.get("variant", "default"))
        if source is not game:
            label = f"{game.name} / {source.name}"
        documents = read_documents_upload(game, request.POST.get("documents", ""))
        check_documents(documents)
    except PrototypeError as error:
        messages.error(request, f"{label} : {error}")
        return redirect("proto_home")
    source.documents = documents
    source.save(update_fields=["documents", "updated_at"])
    logger.info("Documents of prototype %s changed by %s", label, request.user)
    messages.success(request, f"{label} : {len(documents)} document(s) enregistré(s).")
    return redirect("proto_home")


@login_required(login_url=LOGIN_URL)
@require_http_methods(["POST"])
def proto_archive(request, key) -> HttpResponse:
    """Replaces the resources of the prototype by the content of a zip archive."""
    game = _prototype(request, key)
    upload = request.FILES.get("archive")
    try:
        if upload is None:
            raise PrototypeError("Aucun fichier envoyé.")
        count = install_archive(game, upload)
    except PrototypeError as error:
        messages.error(request, f"{game.name} : {error}")
        return redirect("proto_home")
    logger.info("Resources of prototype %s uploaded by %s: %s files", game.name, request.user, count)
    messages.success(request, f"{game.name} : {count} fichier(s) installé(s).")
    return redirect("proto_home")


@login_required(login_url=LOGIN_URL)
@require_http_methods(["POST"])
def proto_key(request, key) -> HttpResponse:
    """Changes the key the lobby asks for. A developer cannot make the game public."""
    game = _prototype(request, key)
    prototype_key = (request.POST.get("prototype_key") or "").strip()
    if not prototype_key or len(prototype_key) > 64:
        messages.error(request, f"{game.name} : la clé doit faire de 1 à 64 caractères.")
        return redirect("proto_home")
    game.prototype_key = prototype_key
    game.save(update_fields=["prototype_key", "updated_at"])
    logger.info("Key of prototype %s changed by %s", game.name, request.user)
    messages.success(request, f"{game.name} : clé changée.")
    return redirect("proto_home")
