import json
from pathlib import Path

import pytest

from app.openapi import (
    OpenApiSpecError,
    default_openapi_path,
    load_openapi_definition,
)


pytestmark = pytest.mark.unit


def test_loads_expected_tools_from_external_openapi() -> None:
    definition = load_openapi_definition()

    assert definition.base_url == "https://open.neis.go.kr"
    assert [operation.name for operation in definition.operations] == [
        "getSchoolInfo",
        "getMealServiceDietInfo",
    ]
    assert [operation.path for operation in definition.operations] == [
        "/hub/schoolInfo",
        "/hub/mealServiceDietInfo",
    ]


def test_hides_credentials_and_enforces_json_and_lunch() -> None:
    definition = load_openapi_definition()
    school_schema = definition.operation("getSchoolInfo").input_schema
    meal_schema = definition.operation(
        "getMealServiceDietInfo"
    ).input_schema

    assert school_schema["additionalProperties"] is False
    assert "Key" not in school_schema["properties"]
    assert school_schema["properties"]["Type"]["enum"] == ["json"]
    assert school_schema["properties"]["pIndex"]["default"] == 1
    assert school_schema["properties"]["pSize"]["default"] == 100
    assert meal_schema["required"] == [
        "ATPT_OFCDC_SC_CODE",
        "SD_SCHUL_CODE",
    ]
    assert meal_schema["properties"]["MMEAL_SC_CODE"]["enum"] == ["2"]
    assert "Key" not in meal_schema["properties"]


def test_missing_spec_fails_explicitly(tmp_path: Path) -> None:
    with pytest.raises(OpenApiSpecError, match="Unable to read"):
        load_openapi_definition(tmp_path / "missing.json")


def test_missing_required_operation_fails_as_a_whole(
    tmp_path: Path,
) -> None:
    document = json.loads(
        default_openapi_path().read_text(encoding="utf-8")
    )
    del document["paths"]["/hub/mealServiceDietInfo"]
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpenApiSpecError, match="getMealServiceDietInfo"):
        load_openapi_definition(spec_path)
