#!/usr/bin/env python
"""Seeds the ISOLATED local browser-QA database (audit_settings) with PREREQUISITES only.

Run: .claude/run_qa.ps1 scripts/seed_browser_qa.py
Everything goes through the real service layer. No workflow outcomes are seeded: no requests, work orders, PM
generations, reservations, issues or closures exist afterwards; the browser run must create them.
Passwords are random, local-only, and written to the git-ignored .env.browser-qa-users (never printed).
"""
import os
import secrets
import sys
from datetime import date, time, timedelta
from pathlib import Path

if os.environ.get("DJANGO_SETTINGS_MODULE") != "audit_settings":
    sys.exit("Refusing: run only with the browser_qa settings (.claude/run_qa.ps1).")
sys.path.insert(0, "/home/user/Fieldops_Nexus/src")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.accounts import services as accounts  # noqa: E402
from apps.assets import hierarchy  # noqa: E402
from apps.assets import services as A  # noqa: E402
from apps.assets.attributes import parse_text  # noqa: E402
from apps.checklists import services as CL  # noqa: E402
from apps.contracts import services as C  # noqa: E402
from apps.core.tenant import tenant_context  # noqa: E402
from apps.inventory import services as I  # noqa: E402
from apps.maintenance import services as PM  # noqa: E402
from apps.portal import services as P  # noqa: E402
from apps.rbac import services as rbac  # noqa: E402
from apps.sites import services as S  # noqa: E402
from apps.sla import services as SLA  # noqa: E402
from apps.tenancy import services as T  # noqa: E402
from apps.tenancy.models import Membership, Organization  # noqa: E402

User = get_user_model()
USERS_FILE = Path(".env.browser-qa-users")
creds: dict[str, str] = {}


def pw() -> str:
    return secrets.token_urlsafe(14) + "Aa1!"


def activate(email, password):
    u = User.objects.get(email=email)
    u.set_password(password)
    u.save()
    accounts.activate_pending_memberships(u)
    creds[email] = password


if Organization.objects.filter(slug__in=["alpha-field-services", "beta-industries"]).exists():
    sys.exit("QA orgs already seeded; refusing to seed twice (no reset is ever performed).")

from django.db import transaction  # noqa: E402

_tx = transaction.atomic()
_tx.__enter__()

# --- platform admin -----------------------------------------------------------------------------------------
admin_email = "superadmin@platform.qa.test"
admin = User.objects.create_user(email=admin_email, password=(p := pw()), full_name="QA Platform Admin",
                                 is_platform_admin=True)
creds[admin_email] = p

# --- organizations + members ---------------------------------------------------------------------------------
alpha, alpha_owner_m = T.create_organization(name="Alpha Field Services", slug="alpha-field-services",
                                             owner_email="owner@alpha.qa.test", owner_name="Alpha Owner",
                                             actor=admin, timezone_name="Asia/Kolkata", country="IN")
beta, beta_owner_m = T.create_organization(name="Beta Industries", slug="beta-industries",
                                           owner_email="owner@beta.qa.test", owner_name="Beta Owner",
                                           actor=admin, timezone_name="Asia/Kolkata", country="IN")
activate("owner@alpha.qa.test", pw())
activate("owner@beta.qa.test", pw())
owner_a = User.objects.get(email="owner@alpha.qa.test")
owner_b = User.objects.get(email="owner@beta.qa.test")

ROLES_ALPHA = [
    ("admin@alpha.qa.test", "Alpha Admin", "admin"),
    ("ops@alpha.qa.test", "Alpha Operations", "operations_manager"),
    ("supervisor@alpha.qa.test", "Alpha Supervisor", "supervisor"),
    ("assets@alpha.qa.test", "Alpha Asset Manager", "asset_manager"),
    ("planner@alpha.qa.test", "Alpha Planner", "maintenance_planner"),
    ("tech1@alpha.qa.test", "Alpha Technician One", "technician"),
    ("tech2@alpha.qa.test", "Alpha Technician Two", "technician"),
    ("stores@alpha.qa.test", "Alpha Stores", "stores_manager"),
    ("service@alpha.qa.test", "Alpha Service Manager", "service_manager"),
    ("auditor@alpha.qa.test", "Alpha Auditor", "auditor"),
    ("client@alpha.qa.test", "Alpha Client", "client_requester"),
]
member = {}
with tenant_context(alpha):
    for email, name, key in ROLES_ALPHA:
        role = rbac.system_role_by_key(alpha, key)
        member[key if key != "technician" else email.split("@")[0]] = T.invite_member(
            alpha, email=email, full_name=name, role_ids=[role.pk], actor=owner_a)
        activate(email, pw())
with tenant_context(beta):
    for email, name, key in [("tech@beta.qa.test", "Beta Technician", "technician")]:
        role = rbac.system_role_by_key(beta, key)
        T.invite_member(beta, email=email, full_name=name, role_ids=[role.pk], actor=owner_b)
        activate(email, pw())


def mem(org, email):
    return Membership.objects.get(organization=org, user__email=email)


# --- ALPHA prerequisites ------------------------------------------------------------------------------------------
with tenant_context(alpha):
    o = owner_a
    hyd = S.create_site(alpha, actor=o, code="HYD-1", name="Hyderabad Operations Site", city="Hyderabad",
                        country="IN", timezone="Asia/Kolkata", address="Plot 12, Madhapur Industrial Area",
                        contact_name="Hyderabad Plant Manager", contact_phone="+91 40 5550 0100")
    blr = S.create_site(alpha, actor=o, code="BLR-1", name="Bangalore Service Depot", city="Bangalore",
                        country="IN", timezone="Asia/Kolkata", address="14 Peenya Industrial Estate")
    bld_a = S.create_zone(hyd, actor=o, name="Building A", zone_type="BUILDING", code="BLD-A")
    gen_room = S.create_zone(hyd, actor=o, name="Generator Room", zone_type="SERVICE_AREA", parent=bld_a)
    S.create_zone(hyd, actor=o, name="Building B", zone_type="BUILDING", code="BLD-B")
    wh_zone = S.create_zone(blr, actor=o, name="Warehouse", zone_type="BUILDING")
    for site in (hyd, blr):
        cal = S.create_calendar(site, actor=o, name="Day shift", working_days=[1, 2, 3, 4, 5, 6],
                                start_time=time(8), end_time=time(18))
        S.add_holiday(cal, date=date(2026, 12, 25), name="Christmas", actor=o)
        S.add_contact(site, actor=o, name=f"{site.code} Site Manager", role_title="Site Manager",
                      phone="+91 40 5550 0101", email=f"manager.{site.code.lower()}@alpha.qa.test")
        S.add_contact(site, actor=o, name="Regional Head", role_title="Escalation", phone="+91 40 5550 0199")

    cat = {}
    cat["Generator"] = A.create_category(alpha, name="Generator", actor=o, attribute_definitions=parse_text(
        "Rated power kVA | number | required\nFuel type | choice | required | Diesel, Gas\nInstalled by | text"))
    for n in ("Pump", "HVAC", "Motor", "IT Equipment", "Vehicle"):
        cat[n] = A.create_category(alpha, name=n, actor=o)

    gen = A.create_asset(alpha, site=hyd, zone=gen_room, category=cat["Generator"], actor=o, asset_tag="GEN-001",
                         name="Diesel Generator 500 kVA", manufacturer="Cummins", model="C500D5",
                         serial_number="CU-500-8841",
                         attributes={"rated_power_kva": "500", "fuel_type": "Diesel"})
    engine = A.create_asset(alpha, site=hyd, zone=gen_room, category=cat["Motor"], actor=o,
                            asset_tag="GEN-001-ENG", name="Engine assembly", manufacturer="Cummins")
    pump = A.create_asset(alpha, site=hyd, zone=gen_room, category=cat["Pump"], actor=o, asset_tag="PMP-001",
                          name="Coolant Pump", manufacturer="Grundfos", serial_number="GF-1182")
    hvac = A.create_asset(alpha, site=hyd, zone=bld_a, category=cat["HVAC"], actor=o, asset_tag="HVAC-001",
                          name="Building A HVAC Unit", manufacturer="Daikin")
    A.create_asset(alpha, site=hyd, zone=bld_a, category=cat["IT Equipment"], actor=o, asset_tag="LAP-001",
                   name="Field Laptop", manufacturer="Dell")
    A.create_asset(alpha, site=blr, zone=wh_zone, category=cat["Vehicle"], actor=o, asset_tag="VEH-001",
                   name="Service Van", manufacturer="Tata")
    hierarchy.add_component(gen, engine, relationship_type="ASSEMBLY", actor=o)
    hierarchy.add_component(engine, pump, relationship_type="COMPONENT", actor=o)
    A.add_document(gen, SimpleUploadedFile("gen001-manual.txt", b"GEN-001 operating manual (QA)"),
                   title="Operating manual", doc_type="MANUAL", actor=o)
    run_hours = A.create_meter(gen, name="Run hours", unit="h", actor=o)
    for v in (100, 220, 340):
        A.record_reading(run_hours, value=v, actor=o)

    # PM plans (schedules only; the browser triggers generation)
    plan_t = PM.create_plan(alpha, asset=gen, name="GEN-001 monthly service", priority="MEDIUM", actor=o)
    PM.create_schedule(plan_t, actor=o, trigger_type="TIME", frequency="MONTHLY", interval_count=1,
                       start_date=timezone.localdate() - timedelta(days=1))
    plan_m = PM.create_plan(alpha, asset=gen, name="GEN-001 500-hour service", priority="HIGH", actor=o)
    PM.create_schedule(plan_m, actor=o, trigger_type="METER", meter=run_hours, interval_value=500, start_value=0)

    # Checklists
    tmpl = CL.create_template(alpha, actor=o, name="Generator corrective inspection", work_type="CORRECTIVE",
                              is_required=True)
    for spec in [
        {"prompt": "Visible leaks present", "item_type": "BOOLEAN"},
        {"prompt": "Output voltage", "item_type": "NUMERIC", "min_value": "380", "max_value": "440", "unit": "V"},
        {"prompt": "Fuel condition", "item_type": "SELECTION", "options": ["Good", "Contaminated", "Low"],
         "exception_options": ["Contaminated"]},
        {"prompt": "Technician remarks", "item_type": "TEXT", "required": False},
    ]:
        CL.add_item(tmpl, actor=o, **spec)
    CL.activate_template(tmpl, actor=o)
    ptmpl = CL.create_template(alpha, actor=o, name="Generator preventive service", work_type="PREVENTIVE",
                               is_required=True)
    CL.add_item(ptmpl, actor=o, prompt="Oil level checked", item_type="BOOLEAN")
    CL.add_item(ptmpl, actor=o, prompt="Coolant level (%)", item_type="NUMERIC", min_value="50", max_value="100",
                unit="%")
    CL.activate_template(ptmpl, actor=o)

    # Inventory
    wh = I.create_warehouse(alpha, site=hyd, code="HYD-WH", name="Hyderabad Store", actor=o)
    wh2 = I.create_warehouse(alpha, site=blr, code="BLR-WH", name="Bangalore Store", actor=o)
    parts = [I.create_part(alpha, part_number=n, name=nm, unit="pcs", actor=o)
             for n, nm in (("BRG-6205", "Bearing 6205"), ("FLT-OIL-01", "Oil filter"), ("BELT-A42", "Drive belt"))]
    for prt, qty in zip(parts, (20, 15, 8), strict=True):
        I.receive(wh, prt, qty, actor=o, reference="QA opening stock")
    I.receive(wh2, parts[0], 5, actor=o, reference="QA opening stock")

    # Contract + SLA
    prof = SLA.create_profile(alpha, name="Standard request SLA", applies_to="REQUEST", actor=o,
                              pause_states=["REQUEST:TRIAGED"])
    for prio, resp, resol in (("LOW", 480, 2880), ("MEDIUM", 240, 1440), ("HIGH", 30, 240), ("CRITICAL", 15, 120)):
        SLA.set_target(prof, priority=prio, response_minutes=resp, resolution_minutes=resol, actor=o)
    sm_role = rbac.system_role_by_key(alpha, "service_manager")
    SLA.create_rule(prof, target_kind="RESPONSE", trigger="WARNING", notify_assignee=False, notify_role=sm_role,
                    after_minutes=0, level=1, actor=o)
    SLA.create_rule(prof, target_kind="RESPONSE", trigger="BREACH", notify_role=sm_role, level=1, actor=o)
    SLA.create_rule(prof, target_kind="RESOLUTION", trigger="BREACH", notify_role=sm_role, level=1, actor=o)
    wo_prof = SLA.create_profile(alpha, name="Standard work-order SLA", applies_to="WORK_ORDER", actor=o)
    for prio, resp, resol in (("LOW", 480, 2880), ("MEDIUM", 240, 1440), ("HIGH", 60, 480), ("URGENT", 15, 240)):
        SLA.set_target(wo_prof, priority=prio, response_minutes=resp, resolution_minutes=resol, actor=o)
    provider = C.create_provider(alpha, name="Cummins Service India", contact_name="AMC Desk",
                                 email="amc@cummins.qa.test", phone="+91 80 5550 0300", actor=o)
    C.create_agreement(alpha, kind="AMC", reference="AMC-GEN-2026", title="GEN-001 annual maintenance contract",
                       provider=provider, site=hyd, start_date=date(2026, 1, 1), end_date=date(2027, 12, 31),
                       assets=[gen], terms="Parts and labour for breakdowns.", exclusion_notes="Fuel excluded.",
                       sla_terms="HIGH: 4h resolution", sla_profile=prof, actor=o)

    # Client portal
    acct = P.enable_account(alpha, mem(alpha, "client@alpha.qa.test"), company="Acme Tenant Ltd", actor=o)
    for a in (gen, hvac):
        P.grant_asset(acct, a, actor=o)

# --- BETA prerequisites ------------------------------------------------------------------------------------------
with tenant_context(beta):
    o = owner_b
    bsite = S.create_site(beta, actor=o, code="PUN-1", name="Pune Plant", city="Pune", country="IN",
                          timezone="Asia/Kolkata", address="Chakan MIDC")
    bzone = S.create_zone(bsite, actor=o, name="Block 1", zone_type="BUILDING")
    bcat = A.create_category(beta, name="Compressor", actor=o)
    A.create_asset(beta, site=bsite, zone=bzone, category=bcat, actor=o, asset_tag="BETA-CMP-001",
                   name="Beta Air Compressor", manufacturer="Atlas Copco")
    bwh = I.create_warehouse(beta, site=bsite, code="PUN-WH", name="Pune Store", actor=o)
    bpart = I.create_part(beta, part_number="BETA-FLT-9", name="Beta Air filter", unit="pcs", actor=o)
    I.receive(bwh, bpart, 10, actor=o, reference="QA opening stock")

_tx.__exit__(None, None, None)
USERS_FILE.write_text("# LOCAL browser-QA passwords (git-ignored). Never commit or paste.\n"
                      + "".join(f"{e}={p}\n" for e, p in creds.items()))
print(f"Seeded: 2 orgs, {len(creds)} accounts. Credentials written to {USERS_FILE} (not printed).")
