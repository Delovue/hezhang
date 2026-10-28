import pytest

from tests.conftest import register_actor


def test_oversized_identifiers_return_validation_errors(client):
    actor = register_actor(client, "alice")
    headers = actor["headers"]
    activity = client.post("/api/v1/activities", headers=headers, json={"name": "边界验证"}).json()
    base = f"/api/v1/activities/{activity['id']}"
    oversized = 10**100
    for path, params in [
        (f"/api/v1/activities/{oversized}", {}),
        (f"{base}/expenses/{oversized}", {}),
        (f"{base}/expenses", {"payer_member_id": oversized}),
        ("/api/v1/activities", {"offset": oversized}),
        (f"{base}/expenses", {"offset": oversized}),
        (f"{base}/audit-logs", {"offset": oversized}),
    ]:
        response = client.get(path, headers=headers, params=params)
        assert response.status_code == 422, (path, response.text)


@pytest.mark.parametrize("invalid_id", [0, -1, 9_007_199_254_740_992])
def test_invalid_path_and_body_identifiers(client, actors, group, expense_data, invalid_id):
    headers = actors["alice"]["headers"]
    assert client.get(f"/api/v1/activities/{invalid_id}", headers=headers).status_code == 422
    base = f"/api/v1/activities/{group['id']}/expenses"
    for change in [
        {"payer_member_id": invalid_id},
        {"participants": [{"member_id": invalid_id}]},
    ]:
        assert client.post(base, headers=headers, json=expense_data | change).status_code == 422
    assert (
        client.delete(f"{base}/1", headers=headers, params={"version": invalid_id}).status_code
        == 422
    )
    assert client.get(base, headers=headers).json() == []
