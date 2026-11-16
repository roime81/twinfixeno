from types import SimpleNamespace

import pytest

import server


def make_context(headers=None):
    request = SimpleNamespace(headers=headers or {})
    request_context = SimpleNamespace(request=request)
    return SimpleNamespace(request_context=request_context)


def test_invoke_forwards_caller_bearer_token(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        content = b'{"items": []}'

        @staticmethod
        def json():
            return {"items": []}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return Response()

    monkeypatch.setattr(server.requests, "request", fake_request)
    result = server.invoke(
        make_context({"authorization": "Bearer caller-token"}),
        "GET",
        "/api/v1/patients/1/timeline",
    )

    assert result == {"items": []}
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/api/v1/patients/1/timeline")
    assert captured["headers"]["Authorization"] == "Bearer caller-token"
    assert captured["timeout"] == (5, 120)


def test_invoke_rejects_missing_or_non_bearer_authorization():
    with pytest.raises(ValueError, match="Authenticated Keycloak bearer token required"):
        server.invoke(make_context({}), "GET", "/api/v1/patients/1/timeline")

    with pytest.raises(ValueError, match="Authenticated Keycloak bearer token required"):
        server.invoke(
            make_context({"authorization": "Basic dXNlcjpwYXNz"}),
            "GET",
            "/api/v1/patients/1/timeline",
        )


def test_invoke_does_not_echo_api_response_body_in_tool_error(monkeypatch):
    class Response:
        status_code = 403
        content = b'{"detail":"patient name or clinical record must never be echoed here"}'
        text = content.decode()

    monkeypatch.setattr(server.requests, "request", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="HTTP 403") as error:
        server.invoke(
            make_context({"authorization": "Bearer caller-token"}),
            "GET",
            "/api/v1/patients/99/timeline",
        )

    assert "patient name" not in str(error.value)


def test_invoke_handles_empty_success_response(monkeypatch):
    class Response:
        status_code = 204
        content = b""

    monkeypatch.setattr(server.requests, "request", lambda *args, **kwargs: Response())
    result = server.invoke(
        make_context({"authorization": "Bearer caller-token"}),
        "DELETE",
        "/api/v1/patients/1/access-grants/1",
    )
    assert result == {"status": "ok"}
