#!/usr/bin/env python
"""HTTP smoke test of a running stack, behaving like a browser (cookies, CSRF token, Origin header).
Needs no credentials: a login POST with a wrong password must come back as a normal form error (CSRF accepted),
not a 403. Usage: python scripts/smoke_stack.py [http://localhost:8080]
"""
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def get(path):
    try:
        r = opener.open(base + path, timeout=15)
        return r.status, r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers


for path in ["/health/live/", "/health/ready/", "/static/lib/bootstrap.min.css", "/static/css/app.css",
             "/api/v1/schema/", "/api/v1/docs/"]:
    status, _, _ = get(path)
    check(f"GET {path} -> 200", status == 200, str(status))

status, html, headers = get("/accounts/login/")
check("login page renders", status == 200 and "Sign in" in html)
check("doctype is first bytes (no BOM)", html.lstrip("﻿").startswith("<!doctype html>") and not html.startswith("﻿"))
token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
check("csrf token present", bool(token))

data = urllib.parse.urlencode({"csrfmiddlewaretoken": token.group(1) if token else "", "username": "nobody@example.test",
                               "password": "definitely-wrong-password-1"}).encode()
req = urllib.request.Request(base + "/accounts/login/", data=data, headers={"Origin": base, "Referer": base + "/accounts/login/"})
try:
    r = opener.open(req, timeout=15)
    status, body = r.status, r.read().decode("utf-8", "replace")
except urllib.error.HTTPError as e:
    status, body = e.code, e.read().decode("utf-8", "replace")
check("login POST passes CSRF (form error, not 403)", status == 200 and "Invalid email or password" in body, str(status))

status, _, h = get("/app/")
check("anonymous /app/ redirects to login", "login" in (opener.open(base + "/app/").url if status == 200 else ""), str(status))
check("security headers present", h.get("X-Frame-Options") == "DENY" and h.get("X-Content-Type-Options") == "nosniff")

sys.exit(1 if failures else 0)
