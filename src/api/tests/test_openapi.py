import json
from pathlib import Path

from jsonschema import Draft202012Validator

from app.main import app


CONTRACT_PATH = Path(__file__).parents[2] / "openapi.json"


def test_committed_contract_matches_fastapi_output():
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert committed == app.openapi()
    assert committed["openapi"] == "3.1.0"
    assert set(committed["paths"]) == {
        "/api/v1/schools",
        "/api/v1/meals",
    }


def test_contract_parameters_match_approved_api():
    contract = app.openapi()
    schools = contract["paths"]["/api/v1/schools"]["get"]["parameters"]
    meals = contract["paths"]["/api/v1/meals"]["get"]["parameters"]

    assert [parameter["name"] for parameter in schools] == [
        "query",
        "page",
        "pageSize",
    ]
    assert schools[0]["schema"]["minLength"] == 2
    assert schools[0]["schema"]["maxLength"] == 100
    assert schools[2]["schema"]["maximum"] == 100
    assert [parameter["name"] for parameter in meals] == [
        "educationOfficeCode",
        "schoolCode",
        "from",
        "to",
    ]
    assert meals[2]["schema"]["format"] == "date"
    assert meals[3]["schema"]["format"] == "date"


def test_contract_schemas_are_json_schema_2020_12_and_errors_are_problem_json():
    contract = app.openapi()

    for schema in contract["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)

    for path in contract["paths"].values():
        responses = path["get"]["responses"]
        assert list(responses["200"]["content"]) == ["application/json"]
        for status, response in responses.items():
            if status != "200":
                assert list(response["content"]) == ["application/problem+json"]
                assert response["content"]["application/problem+json"]["schema"] == {
                    "$ref": "#/components/schemas/ProblemDetails"
                }
