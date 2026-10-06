from django.test import Client


def test_root_is_public_homepage(db):
    r = Client().get("/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Enterprise Operations." in body and 'href="/login/"' in body and "<form" not in body


def test_login_route_serves_login(db):
    r = Client().get("/login/")
    assert r.status_code == 200 and "password" in r.content.decode().lower()
    assert Client().get("/accounts/login/").status_code == 200
