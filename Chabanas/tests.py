import json
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from Chabanas.tools import validate_request
from Chabanas.params_ext import BAD_REQUEST

class ToolTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_validate_request_success(self):
        # Test avec un JSON valide contenant tous les champs obligatoires
        data = {
            "name": "Test Game",
            "player_nickname": "Player1",
            "player_key": "key1"
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        result = validate_request(request, ["name", "player_nickname", "player_key"])
        
        # Doit retourner le dictionnaire de données
        self.assertEqual(result, data)

    def test_validate_request_missing_mandatory_field(self):
        # Test avec un JSON valide mais il manque un champ obligatoire ("player_key")
        data = {
            "name": "Test Game",
            "player_nickname": "Player1"
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        result = validate_request(request, ["name", "player_nickname", "player_key"])
        
        # Doit retourner une HttpResponse 400
        self.assertIsInstance(result, HttpResponse)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content.decode(), BAD_REQUEST)

    def test_validate_request_invalid_json(self):
        # Test avec un corps de requête qui n'est pas du JSON valide
        request = self.factory.post("/", data="not a valid json", content_type='application/json')
        result = validate_request(request, ["name"])

        # Doit retourner une HttpResponse 400
        self.assertIsInstance(result, HttpResponse)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content.decode(), BAD_REQUEST)

    def test_validate_request_rejects_json_array(self):
        # Un corps JSON valide mais qui n'est pas un objet ne peut pas contenir les champs attendus
        request = self.factory.post("/", data=json.dumps(["name"]), content_type='application/json')
        result = validate_request(request, ["name"])

        self.assertIsInstance(result, HttpResponse)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content.decode(), BAD_REQUEST)

    def test_validate_request_ignores_extra_fields(self):
        data = {
            "name": "Test Game",
            "unexpected": "value",
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        result = validate_request(request, ["name"])

        self.assertEqual(result, data)

    def test_validate_request_empty_mandatory_list(self):
        data = {}
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        result = validate_request(request, [])

        self.assertEqual(result, {})
