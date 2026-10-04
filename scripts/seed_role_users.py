#!/usr/bin/env python
"""Adds the missing role-holder users to the EXISTING Alpha and Beta QA organizations (prerequisites only).

Run: .claude/run_prod.ps1 scripts/seed_role_users.py   (settings come from the git-ignored .env.prod)
Goes through the real service layer (invite -> set password -> activate). No business data is created, nothing is
deleted or reset, existing users are never modified. Passwords are random and appended to the git-ignored
.env.qa-users (never printed). Invitation emails are kept local (locmem) so nothing is sent to *.test addresses.
"""
import os
import secrets
import sys
from pathlib import Path

os.environ["EMAIL_BACKEND"] = "django.core.mail.backends.locmem.EmailBackend"
sys.path.insert(0, "src")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

settings.CELERY_TASK_ALWAYS_EAGER = True

from apps.accounts import services as accounts  # noqa: E402
from apps.core.tenant import tenant_context  # noqa: E402
from apps.rbac import services as rbac  # noqa: E402
from apps.tenancy import services as T  # noqa: E402
from apps.tenancy.models import Membership, Organization  # noqa: E402

User = get_user_model()
USERS_FILE = Path(".env.qa-users")

WANTED = {
    "Alpha": [
        ("admin@alpha.test", "Alpha Admin", "admin"),
        ("ops@alpha.test", "Alpha Operations", "operations_manager"),
        ("supervisor@alpha.test", "Alpha Supervisor", "supervisor"),
        ("assets@alpha.test", "Alpha Asset Manager", "asset_manager"),
        ("stores@alpha.test", "Alpha Stores", "stores_manager"),
        ("service@alpha.test", "Alpha Service Manager", "service_manager"),
    ],
    "Beta": [
        ("admin@beta.test", "Beta Admin", "admin"),
        ("ops@beta.test", "Beta Operations", "operations_manager"),
        ("supervisor@beta.test", "Beta Supervisor", "supervisor"),
        ("tech@beta.test", "Beta Technician", "technician"),
        ("planner@beta.test", "Beta Planner", "maintenance_planner"),
        ("stores@beta.test", "Beta Stores", "stores_manager"),
        ("service@beta.test", "Beta Service Manager", "service_manager"),
        ("client@beta.test", "Beta Client", "client_requester"),
        ("auditor@beta.test", "Beta Auditor", "auditor"),
    ],
}
OWNERS = {"Alpha": "owner@alpha.test", "Beta": "owner@beta.test"}


def password() -> str:
    return secrets.token_urlsafe(14) + "Aa1!"


added = []
for prefix, rows in WANTED.items():
    org = Organization.objects.filter(name__startswith=prefix).order_by("created_at").first()
    owner = User.objects.filter(email=OWNERS[prefix]).first()
    if org is None or owner is None:
        print(f"skip {prefix}: organization or owner not found")
        continue
    with tenant_context(org):
        for email, name, key in rows:
            user = User.objects.filter(email=email).first()
            m = Membership.objects.unscoped().filter(organization=org, user=user).first() if user else None
            if m is not None and m.status == Membership.Status.ACTIVE:
                print(f"exists  {org.name}: {email}")
                continue
            if m is None:
                role = rbac.system_role_by_key(org, key)
                T.invite_member(org, email=email, full_name=name, role_ids=[role.pk], actor=owner)
            user = User.objects.get(email=email)
            pw = password()
            user.set_password(pw)
            user.save()
            accounts.activate_pending_memberships(user)
            with USERS_FILE.open("a", encoding="utf-8") as f:
                f.write(f"{email}={pw}\n")
            added.append(f"{org.name}: {email} ({key})")
print("added:", *added, sep="\n  ")
