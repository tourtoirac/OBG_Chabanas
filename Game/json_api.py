"""Authenticated maintenance API for game and variant definitions."""
import logging
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.tools import validate_request
from Game.models import Game, Variant, clean_documents_field
from Game.tools import return_definition_json

logger = logging.getLogger(__name__)


def admin_secret_required(view):
    """Reject maintenance requests before parsing their body or accessing rows."""
    @wraps(view)
    def authenticated(request, *args, **kwargs):
        secret = settings.OBG_ADMIN_SECRET
        if not secret:
            return HttpResponse("Game JSON API is not configured", status=503)
        supplied = request.headers.get("X-OBG-Admin-Secret", "")
        if not constant_time_compare(supplied, secret):
            return HttpResponse("Forbidden", status=403)
        return view(request, *args, **kwargs)
    return authenticated


def read_request(request, update=False):
    """Validate the selector and, for writes, the replacement and revision."""
    required = ["game_name"]
    if update:
        required += ["game_json", "expected_updated_at"]
    data = validate_request(request, required)
    if not isinstance(data, dict):
        return data
    for field in ("game_name", "variant_name"):
        value = data.get(field, "default")
        if not isinstance(value, str) or not value.strip() or len(value) > 64:
            return HttpResponse(f"Invalid {field}", status=400)
    if update:
        if not isinstance(data["game_json"], dict):
            return HttpResponse("game_json must be an object", status=400)
        if "documents" in data and not isinstance(data["documents"], list):
            return HttpResponse("documents must be a list", status=400)
        if not isinstance(data["expected_updated_at"], str) or not data["expected_updated_at"]:
            return HttpResponse("expected_updated_at must be a nonempty string", status=400)
    return data


def definition(data, lock=False):
    """Select an existing definition, including inactive catalogue entries."""
    variant_name = data.get("variant_name", "default")
    if variant_name == "default":
        query = Game.objects.all()
        if lock:
            query = query.select_for_update()
        return get_object_or_404(query, name=data["game_name"])
    query = Variant.objects.select_related("game")
    if lock:
        # Lock the variant only; the parent definition is not being changed.
        query = query.select_for_update(of=("self",))
    return get_object_or_404(query, game__name=data["game_name"], name=variant_name)


@csrf_exempt
@require_http_methods(["POST"])
@admin_secret_required
def get_game_json(request):
    """Return the stored definition and the revision required for its update."""
    data = read_request(request)
    if not isinstance(data, dict):
        return data
    return JsonResponse(return_definition_json(definition(data)))


@csrf_exempt
@require_http_methods(["POST"])
@admin_secret_required
def update_game_json(request):
    """Replace a definition atomically without overwriting a concurrent edit."""
    data = read_request(request, update=True)
    if not isinstance(data, dict):
        return data
    with transaction.atomic():
        row = definition(data, lock=True)
        if row.updated_at.isoformat() != data["expected_updated_at"]:
            return HttpResponse("Definition changed; read it again before updating", status=409)
        # Never save options, catalogue metadata or existing session state.
        # The documents are changed only when the request carries them.
        changed = []
        if row.game_json != data["game_json"]:
            row.game_json = data["game_json"]
            changed.append("game_json")
        if "documents" in data and row.documents != data["documents"]:
            row.documents = data["documents"]
            try:
                clean_documents_field(row)
            except ValidationError:
                return HttpResponse('documents must be a list of {"src": ..., "name": ...}', status=400)
            changed.append("documents")
        if changed:
            row.save(update_fields=changed + ["updated_at"])
            logger.info("Updated %s for %s (%s)", " and ".join(changed), row.name, row.key)
        result = return_definition_json(row)
    return JsonResponse(result)
