from app.errors import ErrorResponse
from tests.test_api_errors import assert_error


def test_openapi_matches_business_error_contract_and_keeps_success_models(client):
    schema = client.get("/openapi.json").json()
    checked = 0
    for path, methods in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in methods.items():
            if method not in {"get", "post", "patch", "delete"}:
                continue
            for status in ["401", "403", "404", "409", "422", "500", "503"]:
                documented = operation["responses"][status]["content"]["application/json"]["schema"]
                assert documented == {"$ref": "#/components/schemas/ErrorResponse"}, (
                    path,
                    method,
                    status,
                )
            checked += 1
    assert checked > 0
    errors = schema["components"]["schemas"]["ErrorResponse"]
    assert set(errors["required"]) == {"detail", "code", "retryable"}
    create = schema["paths"]["/api/v1/activities/{activity_id}/expenses"]["post"]["responses"]
    for status in ["200", "201"]:
        assert create[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ExpenseRead"
        }
    assert create["409"]["headers"]["Retry-After"]["schema"]["type"] == "integer"
    assert (
        "content"
        not in schema["paths"]["/api/v1/activities/{activity_id}/expenses/{expense_id}"]["delete"][
            "responses"
        ]["204"]
    )
    assert "ErrorResponse" not in str(schema["paths"]["/health"]["get"]["responses"])


def test_nested_validation_locations_remain_usable_by_forms(client, actors, group, expense_data):
    response = client.post(
        f"/api/v1/activities/{group['id']}/expenses",
        headers=actors["alice"]["headers"],
        json=expense_data | {"participants": [{"member_id": "not-an-id"}]},
    )
    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["detail"][0]["loc"] == ["body", "participants", 0, "member_id"]
    parsed = ErrorResponse.model_validate(body)
    assert isinstance(parsed.detail[0].loc[2], int)
