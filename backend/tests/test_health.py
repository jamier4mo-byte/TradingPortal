def test_health(client) -> None:
    body = client.get("/api/health").json()
    assert body["app"] == "Trading Portal"
    assert body["db_ok"] is True


def test_unknown_api_path_is_not_the_spa(client) -> None:
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found"}
