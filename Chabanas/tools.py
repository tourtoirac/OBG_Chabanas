import logging

from django.http import HttpResponse
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from Chabanas.params_ext import BAD_REQUEST

logger = logging.getLogger(__name__)

def validate_request(request, mandatory_values):
    # checks if json is valid and extracts data dictionary
    try:
        data = JSONParser().parse(request)
    except ParseError:
        logger.exception("Unable to parse request")
        return HttpResponse(BAD_REQUEST, status=400)

    for value in mandatory_values:
        if value not in data:
            return HttpResponse(BAD_REQUEST, status=400)
    return data
