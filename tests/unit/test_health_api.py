"""Health API keeps service available with component failures (T147)."""


def test_health_reports_failures_without_http_collapse():
    from personal_brain_server.api.health import health_response

    response = health_response(components={"db": "healthy", "assets": "failed"})
    assert response["service"] == "available"
    assert response["overall"] == "failed"
    assert response["components"]["assets"] == "failed"
