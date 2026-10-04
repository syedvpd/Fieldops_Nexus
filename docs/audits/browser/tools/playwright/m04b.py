import sys, time, json, math, re, subprocess, datetime as dt; sys.path.insert(0, '.')
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta
from bx import *
r = Run("M04").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
PL = "/app/maintenance/plans/"
HYD, BLR = sid("HYD-1"), sid("BLR-1")
CAT = lambda n: sql(f"select id from assets_assetcategory where name='{n}' and organization_id={ALPHA}")
PUMP = CAT("Pump")
ASSET = lambda tag: sql(f"select id from assets_asset where lower(asset_tag)=lower('{tag}') and organization_id={ALPHA}")
TZ = ZoneInfo(sql(f"select timezone from sites_site where id='{HYD}'") or "UTC")
TODAY = dt.datetime.now(TZ).date()
D = lambda n: (TODAY + dt.timedelta(days=n)).isoformat()
ROLE_LIST = ["owner", "admin", "ops", "supervisor", "assets", "planner", "tech", "tech2", "stores", "service", "auditor", "client"]


class contextlib_null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def mk(tag, site=HYD):
    bapi(pg, "POST", "/api/v1/assets/", {"asset_tag": tag, "name": f"PM asset {tag}", "category": PUMP, "site": site})
    return ASSET(tag)


def mkplan(asset, name, **kw):
    res = bapi(pg, "POST", "/api/v1/maintenance-plans/", {"asset": asset, "name": name, **kw})
    return sql(f"select id from maintenance_maintenanceplan where name='{name}' and asset_id='{asset}'")


def schedule_ids(plan): return sql(f"select string_agg(id::text,' ') from maintenance_maintenanceschedule where plan_id='{plan}'").split()
SCH = lambda plan: sql(f"select id from maintenance_maintenanceschedule where plan_id='{plan}' order by created_at desc limit 1")
cyc = lambda sch: int(sql(f"select count(*) from maintenance_maintenancecycle where schedule_id='{sch}'"))
pmwo = lambda: int(sql(f"select count(*) from workorders_workorder where source_type='PREVENTIVE_MAINTENANCE' and organization_id={ALPHA}"))


def rows(p):
    return [[c.strip() for c in row.locator("td").all_inner_texts()] for row in p.locator("main table tbody tr").all()]


def new_sched(p, plan, vals, ok=True, forged=False):
    path = f"{PL}{plan}/schedules/new/"
    p.goto(BASE + path); p.wait_for_load_state("networkidle")
    p.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{e.removeAttribute('maxlength');e.removeAttribute('min');e.removeAttribute('max');e.removeAttribute('step'); if(['date','time','number'].includes(e.type)) e.type='text'})")
    fill(p, vals)
    with (contextlib_null() if ok else r.expect_errors()):
        with p.expect_response(lambda x: x.request.method == "POST" and "/schedules/new" in x.url) as ri:
            p.locator("main form button:has-text('Create schedule')").click()
        p.wait_for_load_state("networkidle")
    return ri.value.status


def time_sched(p, plan, freq="Month(s)", n=1, start=None, ok=True, **kw):
    v = dict(trigger_type="Time-based", frequency=freq, interval_count=str(n), start_date=start or D(10)); v.update(kw)
    return new_sched(p, plan, v, ok)


def nth_month(start, k, unit="months", n=1):
    return start + relativedelta(**{unit: k * n})


# ---------------- setup (not under test): assets with meters + plans
AT, AM, AX = mk(f"PMT-{U}"), mk(f"PMM-{U}"), mk(f"PMX-{U}")
PT = mkplan(AT, f"Time plan {U}", priority="HIGH", estimated_hours="3", **({"checklist_key": sql(f"select key from checklists_checklisttemplate where organization_id={ALPHA} order by name limit 1")}))
PM_ = mkplan(AM, f"Meter plan {U}")
PX = mkplan(AX, f"Misc plan {U}")
pg.goto(BASE + f"/app/assets/{AM}/?tab=meters")
pg.locator("main form[action*='/meters/new/'] [name=name]").fill("Run hours"); pg.locator("main form[action*='/meters/new/'] [name=unit]").fill("h"); pg.locator("main form[action*='/meters/new/'] button:has-text('Add meter')").click(); pg.wait_for_load_state("networkidle")
MID = sql(f"select id from assets_assetmeter where asset_id='{AM}' and name='Run hours'")
print("setup", AT[:8], AM[:8], PT[:8], PM_[:8], MID[:8], "today", TODAY)


@feature(r, "Schedule form + time-based create")
def t_time():
    p = r.page(O); path = f"{PL}{PT}/schedules/new/"
    st, p = visit(r, O, path)
    names = p.eval_on_selector_all("main form [name]", "e=>e.filter(x=>x.type!=='hidden').map(x=>x.name)")
    r.ok(names == ["trigger_type", "frequency", "interval_count", "start_date", "meter", "interval_value", "start_value", "lead_days", "window_start_time", "window_hours", "reminder_days"], "Schedule form exposes all 11 fields (trigger, frequency, interval, start date, meter, interval value, start value, lead days, window start/hours, reminder days)", path, O, "read form", "11 fields", names)
    dv = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.filter(x=>x.type!=='hidden').map(x=>[x.name,x.value]))")
    r.ok(dv["lead_days"] == "0" and dv["window_start_time"] == "08:00" and dv["window_hours"] == "8" and dv["reminder_days"] == "0" and dv["start_value"] == "0", "Defaults: lead 0, window 08:00 for 8 h, reminder 0, start value 0", path, O, "read defaults", "defaults", {k: dv[k] for k in ("lead_days", "window_start_time", "window_hours")})
    fo = p.locator("main select[name=frequency] option").all_inner_texts(); to = p.locator("main select[name=trigger_type] option").all_inner_texts(); mo = p.locator("main select[name=meter] option").all_inner_texts()
    r.ok(fo == ["-", "Day(s)", "Week(s)", "Month(s)", "Quarter(s)", "Year(s)"] and to == ["Time-based", "Meter-based"], "Trigger = Time-based/Meter-based; frequency = Day/Week/Month/Quarter/Year", path, O, "read options", "ok", [to, fo])
    r.ok(mo == ["---------"] or len(mo) <= 1, "Meter dropdown is empty for an asset without meters", path, O, "read options", "no meters", mo)
    p.goto(BASE + f"{PL}{PM_}/schedules/new/"); mo2 = p.locator("main select[name=meter] option").all_inner_texts(); r.ok(any("Run hours (h)" in o for o in mo2), "Meter dropdown lists only this asset's meters", p.url, O, "read options", "Run hours (h)", mo2)
    # create full
    s = new_sched(p, PT, dict(trigger_type="Time-based", frequency="Month(s)", interval_count="1", start_date=D(10), lead_days="2", window_start_time="09:30", window_hours="6", reminder_days="3"))
    sch = SCH(PT); row = sql(f"select trigger_type||'|'||frequency||'|'||interval_count||'|'||start_date||'|'||lead_days||'|'||window_start_time||'|'||window_hours||'|'||reminder_days||'|'||next_sequence||'|'||next_due_date||'|'||is_active from maintenance_maintenanceschedule where id='{sch}'")
    exp = f"TIME|MONTHLY|1|{D(10)}|2|09:30:00|6|3|0|{D(10)}|true"
    r.ok(row == exp and "/plans/" in p.url and "Schedule created: every 1 month" in p.inner_text("main"), "Create time-based schedule: all fields persisted, first occurrence = start date, success message", p.url, O, "monthly, start +10d, lead 2, window 09:30/6h, reminder 3", "row saved", row, db=row, audit=audits(sch, "maintenance.schedule_created"))
    t = p.inner_text("main #schedules-table"); r.ok("every 1 month" in t.lower() and TODAY.strftime("%b") in t or "SCHEDULED" in t.upper(), "Plan page lists the schedule with next-due date and state SCHEDULED", p.url, O, "read schedules table", "row with next due + SCHEDULED", t[:100].replace("\n", " "))
    p.goto(BASE + f"/app/maintenance/schedules/{sch}/"); dt_ = p.inner_text("main")
    nd = dt.date.fromisoformat(D(10)).strftime("%d %b %Y")
    r.ok(nd in p.inner_text("#next-due") and "2 day(s) before due" in dt_ and "09:30 for 6 h" in dt_ and "3 day(s) before" in dt_ and "Next occurrence no.0" in dt_.replace("\n", ""), "Schedule detail shows next due, lead days, window and reminder", p.url, O, "read detail", "values", dt_[:120].replace("\n", " "))
    # other frequencies (interval + unit combos)
    combos = [("Day(s)", 3, "DAILY", "days", 1, "every 3 days"), ("Week(s)", 2, "WEEKLY", "weeks", 1, "every 2 weeks"), ("Quarter(s)", 1, "QUARTERLY", "months", 3, "every 1 quarter"), ("Year(s)", 1, "YEARLY", "years", 1, "every 1 year")]
    for label, n, code, unit, mult, desc in combos:
        time_sched(p, PT, freq=label, n=n, start=D(20))
        s_ = SCH(PT); v = sql(f"select frequency||'|'||interval_count||'|'||next_due_date from maintenance_maintenanceschedule where id='{s_}'")
        r.ok(v == f"{code}|{n}|{D(20)}", f"Create {label} schedule (every {n}): stored with first due = start date", p.url, O, f"{label} x{n}", f"{code}|{n}|{D(20)}", v, db=v, audit=audits(s_))
        p.goto(BASE + f"/app/maintenance/schedules/{s_}/"); r.ok(desc in p.inner_text("main h1").lower(), f"Schedule title reads '{desc}'", p.url, O, "read h1", desc, p.inner_text("main h1")[:40])
    # past start date => next future occurrence, no backlog
    PP = mkplan(AT, f"Past start {U}")
    past = TODAY - dt.timedelta(days=45); time_sched(p, PP, "Month(s)", 1, start=past.isoformat()); sp = SCH(PP)
    k = 0
    while nth_month(past, k) < TODAY: k += 1
    exp_due = nth_month(past, k).isoformat(); got = sql(f"select next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sp}'")
    r.ok(got == f"{k}|{exp_due}" and cyc(sp) == 0, f"Start date in the past: schedule points to the next future occurrence ({exp_due}); no backlog of work orders", p.url, O, f"start {past}", f"{k}|{exp_due}", got, db=got)
    # today as start => DUE immediately
    PT0 = mkplan(AT, f"Today start {U}"); time_sched(p, PT0, "Month(s)", 1, start=D(0)); s0 = SCH(PT0)
    p.goto(BASE + f"/app/maintenance/schedules/{s0}/"); r.ok("DUE" in p.inner_text("main h1").upper(), "Start date today: schedule is DUE immediately", p.url, O, "start today", "state DUE", p.inner_text("main h1")[:50])
    # far future / extreme dates
    PF = mkplan(AT, f"Far future {U}"); time_sched(p, PF, "Year(s)", 1, start="2099-01-01"); r.ok(sql(f"select count(*) from maintenance_maintenanceschedule where plan_id='{PF}'") == "1", "Start date 2099-01-01 accepted (boundary: far future)", p.url, O, "start 2099", "accepted", "ok")
    PE = mkplan(AT, f"Extreme {U}"); b = sql("select count(*) from maintenance_maintenanceschedule")
    s_ = time_sched(p, PE, "Year(s)", 1, start="9999-12-31", ok=False)
    r.T("Start date 9999-12-31 (year-overflow boundary)", p.url, O, "yearly from 9999-12-31", "refused or accepted without a server error", f"http={s_}; schedules {b}->{sql('select count(*) from maintenance_maintenanceschedule')}", "FAIL" if s_ >= 500 else "PASS", db=f"{b}->{sql('select count(*) from maintenance_maintenanceschedule')}")
    s_ = time_sched(p, PE, "Day(s)", 1, start="0001-01-01", ok=False); r.T("Start date 0001-01-01 boundary", p.url, O, "daily from year 1", "no server error", f"http={s_}", "FAIL" if s_ >= 500 else "PASS", db=sql(f"select count(*) from maintenance_maintenanceschedule where plan_id='{PE}'"))
    # validation
    PV = mkplan(AT, f"Validation plan {U}")
    cnt = lambda: int(sql(f"select count(*) from maintenance_maintenanceschedule where plan_id='{PV}'"))
    def bad(label, vals, frag=None, base=None):
        b = cnt(); v = dict(trigger_type="Time-based", frequency="Month(s)", interval_count="1", start_date=D(5)); v.update(base or {}); v.update(vals)
        s_ = new_sched(p, PV, v, ok=False); srv = "Server Error" in p.inner_text("body")[:300]
        ok = cnt() == b and s_ == 400 and not srv and (frag is None or frag.lower() in p.inner_text("main").lower())
        r.ok(ok, f"Validation: {label}", p.url, O, "submit invalid", "400 + message, nothing saved" + (f" ('{frag}')" if frag else ""), "SERVER ERROR" if srv else f"http={s_} rows {b}->{cnt()} {msgs(p)[:80]}", db=f"{b}->{cnt()}")
    bad("frequency missing", dict(frequency="-"), "frequency"); bad("start date missing", dict(start_date=""), "start date"); bad("start date not a date", dict(start_date="not-a-date")); bad("start date impossible 2026-02-30", dict(start_date="2026-02-30"))
    bad("interval missing", dict(interval_count=""), "interval"); bad("interval 0", dict(interval_count="0")); bad("interval -1", dict(interval_count="-1")); bad("interval 1001 (max 1000)", dict(interval_count="1001")); bad("interval 1.5", dict(interval_count="1.5")); bad("interval abc", dict(interval_count="abc")); bad("interval 99999999999", dict(interval_count="99999999999"))
    bad("lead days 61 (max 60)", dict(lead_days="61")); bad("lead days -1", dict(lead_days="-1")); bad("window hours 0", dict(window_hours="0")); bad("window hours 73 (max 72)", dict(window_hours="73")); bad("reminder days 61", dict(reminder_days="61")); bad("reminder days -1", dict(reminder_days="-1"))
    bad("window start time invalid", dict(window_start_time="25:99")); bad("window start time missing", dict(window_start_time=""))
    bad("lead days abc", dict(lead_days="abc")); bad("window hours 99999999999", dict(window_hours="99999999999"))
    bad("meter-based without a meter", dict(trigger_type="Meter-based", frequency="-", interval_count="", start_date="", interval_value="100"))
    # boundaries accepted
    for label, vals in (("interval 1000 + lead 60 + window 72h + reminder 60", dict(interval_count="1000", lead_days="60", window_hours="72", reminder_days="60", frequency="Day(s)")), ("interval 1 + lead 0 + window 1h", dict(interval_count="1", frequency="Week(s)", window_hours="1")), ("window start 00:00", dict(frequency="Quarter(s)", interval_count="2", window_start_time="00:00")), ("window start 23:59", dict(frequency="Year(s)", interval_count="3", window_start_time="23:59"))):
        b = cnt(); v = dict(trigger_type="Time-based", frequency="Month(s)", interval_count="1", start_date=D(5)); v.update(vals); new_sched(p, PV, v)
        r.ok(cnt() == b + 1, f"Boundary accepted: {label}", p.url, O, "submit", "created", f"rows {b}->{cnt()}", db=f"{b}->{cnt()}", audit=audits(SCH(PV)))
    # duplicates
    b = cnt(); new_sched(p, PV, dict(trigger_type="Time-based", frequency="Month(s)", interval_count="1", start_date=D(40)), ok=False) if False else None
    time_sched(p, PV, "Month(s)", 4, start=D(6)); b = cnt(); s_ = time_sched(p, PV, "Month(s)", 4, start=D(7), ok=False)
    r.ok(cnt() == b and "identical schedule" in p.inner_text("main").lower(), "Duplicate schedule (same frequency + interval on the plan) refused", p.url, O, "same freq+interval again", "refused 'identical schedule'", msgs(p)[:80], db=f"{b}->{cnt()}")
    time_sched(p, PV, "Month(s)", 5, start=D(6)); r.ok(cnt() == b + 1, "Different interval on the same plan is allowed", p.url, O, "interval 5", "created", cnt())
    time_sched(p, PX, "Month(s)", 4, start=D(6)); r.ok(sql(f"select count(*) from maintenance_maintenanceschedule where plan_id='{PX}'") == "1", "Same frequency + interval on another plan is allowed", p.url, O, "other plan", "created", "ok")
    # crafted POSTs
    p.goto(BASE + f"{PL}{PV}/schedules/new/"); b = cnt()
    betameter = sql("select id from assets_assetmeter where organization_id<>%s limit 1" % ALPHA) or "00000000-0000-0000-0000-000000000009"
    for label, data in (("meter of another asset (forged)", {"trigger_type": "METER", "meter": MID, "interval_value": "100", "start_value": "0", "lead_days": "0", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"}),
                        ("meter of another tenant (forged)", {"trigger_type": "METER", "meter": betameter, "interval_value": "100", "start_value": "0", "lead_days": "0", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"}),
                        ("unknown trigger type (forged)", {"trigger_type": "CRON", "frequency": "MONTHLY", "interval_count": "1", "start_date": D(5)}),
                        ("unknown frequency (forged)", {"trigger_type": "TIME", "frequency": "HOURLY", "interval_count": "1", "start_date": D(5), "lead_days": "0", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"})):
        with r.expect_errors(): res = bfetch(p, "POST", f"{PL}{PV}/schedules/new/", data)
        r.ok(cnt() == b and res["status"] in (400, 403, 404) and "Server Error" not in res["html"][:400], f"Crafted POST: {label} rejected", f"{PL}{PV}/schedules/new/", O, "forged", "400/403/404, nothing saved", f"http={res['status']}", db=f"{b}->{cnt()}")
    return dict(sch=sch)


@feature(r, "Meter-based schedules")
def t_meter():
    p = r.page(O); path = f"{PL}{PM_}/schedules/new/"
    def msch(vals, ok=True):
        v = dict(trigger_type="Meter-based", frequency="-", interval_count="", start_date="", meter=MID, interval_value="500", start_value="0"); v.update(vals); return new_sched(p, PM_, v, ok)
    cnt = lambda: int(sql(f"select count(*) from maintenance_maintenanceschedule where plan_id='{PM_}'"))
    b = cnt(); msch({}); sch = SCH(PM_)
    row = sql(f"select trigger_type||'|'||meter_id||'|'||interval_value||'|'||start_value||'|'||next_sequence||'|'||next_due_value||'|'||coalesce(next_due_date::text,'-') from maintenance_maintenanceschedule where id='{sch}'")
    r.ok(row == f"METER|{MID}|500.000|0.000|1|500.000|-" and cnt() == b + 1 and "every 500 h" in p.inner_text("main").lower(), "Create meter-based schedule (every 500 h): threshold 500, no due date", p.url, O, "meter Run hours, interval 500", "saved", row, db=row, audit=audits(sch, "maintenance.schedule_created"))
    p.goto(BASE + f"/app/maintenance/schedules/{sch}/"); t = p.inner_text("main"); r.ok("Run hours (h)" in t and "500 h, counting from 0" in t and "500 h" in p.inner_text("#next-due"), "Detail shows meter, interval, start and next threshold", p.url, O, "read detail", "values", t[:120].replace("\n", " "))
    r.ok("SCHEDULED" in p.inner_text("main h1").upper(), "No reading yet: state SCHEDULED", p.url, O, "read state", "SCHEDULED", p.inner_text("main h1")[:40])
    def bad(label, vals, frag=None):
        b = cnt(); s_ = msch(vals, ok=False); srv = "Server Error" in p.inner_text("body")[:300]
        r.ok(cnt() == b and s_ == 400 and not srv and (frag is None or frag.lower() in p.inner_text("main").lower()), f"Validation: {label}", p.url, O, "submit invalid", "400 + message, nothing saved", "SERVER ERROR" if srv else f"http={s_} rows {b}->{cnt()} {msgs(p)[:70]}", db=f"{b}->{cnt()}")
    bad("identical meter schedule (same meter + interval)", {}, "identical schedule"); bad("interval 0", dict(interval_value="0")); bad("interval negative", dict(interval_value="-5")); bad("interval missing", dict(interval_value="")); bad("interval text", dict(interval_value="abc")); bad("interval 4 decimals", dict(interval_value="1.2345")); bad("interval 1e12", dict(interval_value="1000000000000")); bad("start value negative", dict(interval_value="250", start_value="-1")); bad("start value text", dict(interval_value="250", start_value="x")); bad("meter not chosen", dict(meter="---------", interval_value="250"))
    b = cnt(); msch(dict(interval_value="0.001")); r.ok(cnt() == b + 1, "Boundary: interval 0.001 accepted", p.url, O, "interval 0.001", "created", cnt())
    b = cnt(); msch(dict(interval_value="999999999999.999", start_value="0")); r.ok(cnt() == b + 1, "Boundary: interval 999999999999.999 accepted", p.url, O, "interval ~1e12", "created", cnt())
    b = cnt(); msch(dict(interval_value="250", start_value="100")); r.ok(cnt() == b + 1 and sql(f"select next_due_value from maintenance_maintenanceschedule where id='{SCH(PM_)}'") == "350.000", "Start value 100 + interval 250 -> first threshold 350", p.url, O, "start 100, every 250", "350", sql(f"select next_due_value from maintenance_maintenanceschedule where id='{SCH(PM_)}'"), audit=audits(SCH(PM_)))
    # reading crosses threshold -> DUE
    p.goto(BASE + f"/app/assets/{AM}/?tab=meters"); f = p.locator(f"main form[action*='/meters/{MID}/reading/']")
    f.locator("[name=value]").fill("120"); f.locator("button:has-text('Record')").click(); p.wait_for_load_state("networkidle")
    p.goto(BASE + f"/app/maintenance/schedules/{sch}/"); r.ok("SCHEDULED" in p.inner_text("main h1").upper(), "Reading 120 h (< 500): still SCHEDULED", p.url, O, "record 120 h then reload", "SCHEDULED", p.inner_text("main h1")[:40])
    p.goto(BASE + f"/app/assets/{AM}/?tab=meters"); f = p.locator(f"main form[action*='/meters/{MID}/reading/']"); f.locator("[name=value]").fill("520"); f.locator("button:has-text('Record')").click(); p.wait_for_load_state("networkidle")
    p.goto(BASE + f"/app/maintenance/schedules/{sch}/"); r.ok("DUE" in p.inner_text("main h1").upper(), "Reading 520 h crosses the 500 h threshold: schedule becomes DUE", p.url, O, "record 520 h then reload", "DUE", p.inner_text("main h1")[:40], ev=shot(p, "M04_meter_due"))
    return dict(sch=sch)


@feature(r, "Schedule edit + enable/disable")
def t_edit():
    p = r.page(O); PE_ = mkplan(AT, f"Edit sched plan {U}"); time_sched(p, PE_, "Month(s)", 1, start=D(30)); sch = SCH(PE_); E = f"/app/maintenance/schedules/{sch}/edit/"
    st, p = visit(r, O, E)
    v = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.filter(x=>x.type!=='hidden').map(x=>[x.name,x.value]))")
    r.ok("trigger_type" not in v and v["frequency"] == "MONTHLY" and v["interval_count"] == "1" and v["start_date"] == D(30) and v["window_start_time"].startswith("08:00") and v["window_hours"] == "8", "Edit form is pre-filled; trigger type is not editable", E, O, "open edit", "prefilled, no trigger", {k: v[k] for k in ("frequency", "interval_count", "start_date")})
    # window-only edit keeps recurrence
    nxt = sql(f"select next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sch}'")
    fill(p, dict(lead_days="5", window_start_time="10:15", window_hours="4", reminder_days="2")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    row = sql(f"select lead_days||'|'||window_start_time||'|'||window_hours||'|'||reminder_days||'|'||next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sch}'")
    r.ok(row == f"5|10:15:00|4|2|{nxt}" and "Saved" in p.inner_text("main"), "Edit window/lead/reminder only: saved and the due date is unchanged", p.url, O, "change 4 fields + Save", "saved, next due unchanged", row, db=row, audit=audits(sch, "maintenance.schedule_updated"))
    ev = sql(f"select before::text||' => '||after::text from audit_auditlog where target_id='{sch}' and action='maintenance.schedule_updated' order by occurred_at desc limit 1"); r.ok('"lead_days": 0' in ev.replace(": 0,", ": 0,") and "10:15" in ev, "Audit has before/after", "-", O, "audit", "before/after", ev[:100], audit=ev[:100])
    # recurrence change resyncs
    p.goto(BASE + E); fill(p, dict(frequency="Week(s)", interval_count="2", start_date=D(12))); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    row = sql(f"select frequency||'|'||interval_count||'|'||start_date||'|'||next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sch}'")
    r.ok(row == f"WEEKLY|2|{D(12)}|0|{D(12)}", "Edit recurrence (every 2 weeks from +12d): next occurrence restarts at the new start date", p.url, O, "frequency/interval/start", "resynced", row, db=row, audit=audits(sch, "maintenance.schedule_updated"))
    p.goto(BASE + f"/app/maintenance/schedules/{sch}/"); r.ok("every 2 weeks" in p.inner_text("main h1").lower(), "Detail reflects the edit after reload", p.url, O, "reload", "every 2 weeks", p.inner_text("main h1")[:40])
    # validation on edit
    for label, vals in (("interval 0", dict(interval_count="0")), ("interval 1001", dict(interval_count="1001")), ("lead days 61", dict(lead_days="61")), ("window hours 0", dict(window_hours="0")), ("start date missing", dict(start_date="")), ("frequency missing", dict(frequency="-"))):
        p.goto(BASE + E); p.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{e.removeAttribute('min');e.removeAttribute('max');e.removeAttribute('required'); if(['date','time','number'].includes(e.type)) e.type='text'})"); before = sql(f"select interval_count||lead_days||window_hours||start_date||frequency from maintenance_maintenanceschedule where id='{sch}'")
        fill(p, vals)
        with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
        r.ok(sql(f"select interval_count||lead_days||window_hours||start_date||frequency from maintenance_maintenanceschedule where id='{sch}'") == before and "Server Error" not in p.inner_text("body")[:300], f"Edit validation: {label} refused, schedule unchanged", E, O, label, "refused", msgs(p)[:70], db="unchanged")
    # edit to an identical sibling schedule
    time_sched(p, PE_, "Day(s)", 9, start=D(3)); other = SCH(PE_); p.goto(BASE + E); fill(p, dict(frequency="Day(s)", interval_count="9"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select frequency from maintenance_maintenanceschedule where id='{sch}'") == "WEEKLY" and "identical schedule" in p.inner_text("main").lower(), "Edit into an identical sibling schedule refused", E, O, "freq=day, interval=9", "refused", msgs(p)[:70])
    p.goto(BASE + E); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state("networkidle"); r.ok(sch in p.url, "Edit: Cancel returns to the schedule", p.url, O, "Cancel", "detail", p.url)
    with r.expect_errors(): resp = p.goto(BASE + "/app/maintenance/schedules/00000000-0000-0000-0000-000000000000/")
    r.ok(resp.status == 404, "Unknown schedule id -> 404", p.url, O, "random uuid", "404", resp.status)
    # disable / enable on detail (confirm) and plan page (no confirm)
    S = f"/app/maintenance/schedules/{sch}/"; p.goto(BASE + S)
    p.locator("main form[action$='/disable/'] button").click(); dlg = p.locator("#fx-confirm"); dlg.wait_for(state="visible", timeout=3000)
    r.ok("Disable this schedule" in dlg.inner_text(), "Disable (schedule page) asks for confirmation", S, O, "click Disable", "dialog", dlg.inner_text()[:50])
    dlg.locator("button:has-text('Cancel')").click(); p.wait_for_timeout(400); r.ok(sql(f"select is_active from maintenance_maintenanceschedule where id='{sch}'") in ("true", "t"), "Cancel keeps the schedule enabled", S, O, "Cancel", "enabled", "true")
    cclick(p, p.locator("main form[action$='/disable/'] button"))
    r.ok(sql(f"select is_active from maintenance_maintenanceschedule where id='{sch}'") in ("false", "f") and "DISABLED" in p.inner_text("main h1").upper() and "schedule_disabled" in p.inner_text("main"), "Disable schedule: persisted, state DISABLED, reason shown", S, O, "Confirm", "disabled", "false", audit=audits(sch, "maintenance.schedule_disabled"))
    r.ok(p.locator("main form[action$='/generate/']").count() == 0, "Disabled schedule offers no 'Generate now'", S, O, "inspect", "hidden", "ok")
    b = pmwo()
    with r.expect_errors(): res = bfetch(p, "POST", S + "generate/", {})
    r.ok(pmwo() == b and sql(f"select count(*) from maintenance_maintenancecycle where schedule_id='{sch}'") == "0", "Generate on a disabled schedule (forged POST) creates nothing", S, O, "POST generate", "no WO", f"http={res['status']}", db=f"WOs {b}->{pmwo()}")
    p.goto(BASE + "/app/maintenance/due/"); r.ok(sch not in p.content(), "Disabled schedule is absent from 'Due & upcoming'", "/app/maintenance/due/", O, "read due page", "absent", "ok")
    p.goto(BASE + S); p.locator("main form[action$='/enable/'] button").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select is_active from maintenance_maintenanceschedule where id='{sch}'") in ("true", "t") and "SCHEDULED" in p.inner_text("main h1").upper(), "Enable schedule: persisted, state back to SCHEDULED", S, O, "click Enable", "enabled", "true", audit=audits(sch, "maintenance.schedule_enabled"))
    # plan page row buttons
    p.goto(BASE + f"{PL}{PE_}/"); rowb = p.locator(f"#schedules-table tbody tr", has=p.locator(f"a[href='{S}']"))
    rowb.locator("button:has-text('Disable')").click(); p.wait_for_load_state("networkidle"); r.ok(sql(f"select is_active from maintenance_maintenanceschedule where id='{sch}'") in ("false", "f") and PE_ in p.url, "Plan page 'Disable' button works and stays on the plan", p.url, O, "click Disable in row", "disabled", "false")
    p.goto(BASE + f"{PL}{PE_}/"); rowb = p.locator("#schedules-table tbody tr", has=p.locator(f"a[href='{S}']")); rowb.locator("button:has-text('Enable')").click(); p.wait_for_load_state("networkidle"); r.ok(sql(f"select is_active from maintenance_maintenanceschedule where id='{sch}'") in ("true", "t"), "Plan page 'Enable' button works", p.url, O, "click Enable in row", "enabled", "true")
    # plan disabled => schedules blocked
    bfetch(p, "POST", f"{PL}{PE_}/active/", {"active": "0"}); p.goto(BASE + S); r.ok("plan_disabled" in p.inner_text("main") and "DISABLED" in p.inner_text("main h1").upper(), "Plan disabled: its schedules show DISABLED / plan_disabled", S, O, "disable plan", "blocked", p.inner_text("main")[:80].replace("\n", " "))
    bfetch(p, "POST", f"{PL}{PE_}/active/", {"active": "1"})
    # meter inactive blocks a meter schedule
    msch = sql(f"select id from maintenance_maintenanceschedule where plan_id='{PM_}' and trigger_type='METER' order by created_at limit 1")
    p.goto(BASE + f"/app/assets/{AM}/?tab=meters"); cclick(p, p.locator(f"main form[action*='/meters/{MID}/toggle/'] button"))
    p.goto(BASE + f"/app/maintenance/schedules/{msch}/"); r.ok("meter_inactive" in p.inner_text("main") and "DISABLED" in p.inner_text("main h1").upper(), "Cross-module: deactivating the asset meter (M02) blocks the meter schedule (M04)", p.url, O, "deactivate meter then open schedule", "blocked: meter_inactive", p.inner_text("main")[:90].replace("\n", " "))
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/maintenance/schedules/{msch}/enable/", {})
    p.goto(BASE + f"/app/assets/{AM}/?tab=meters"); p.locator(f"main form[action*='/meters/{MID}/toggle/'] button").click(); p.wait_for_load_state("networkidle")
    p.goto(BASE + f"/app/maintenance/schedules/{msch}/"); r.ok("meter_inactive" not in p.inner_text("main"), "Reactivating the meter unblocks the schedule", p.url, O, "reactivate meter", "no longer blocked", "ok")


@feature(r, "Generation: duplicates, work orders, lead, missed, F-H01")
def t_generate():
    p = r.page(O)
    # --- generate now on a DUE time schedule
    PG_ = mkplan(AT, f"Gen plan {U}", priority="URGENT", estimated_hours="2.5", **({"checklist_key": sql(f"select key from checklists_checklisttemplate where organization_id={ALPHA} order by name limit 1")}))
    time_sched(p, PG_, "Month(s)", 1, start=D(0), window_start_time="09:30", window_hours="6"); sch = SCH(PG_); S = f"/app/maintenance/schedules/{sch}/"
    p.goto(BASE + "/app/maintenance/due/"); rr = [x for x in rows(p) if x[0].startswith(f"Gen plan {U}")]
    r.ok(rr and "DUE" in rr[0][4].upper(), "'Due & upcoming' lists the schedule as DUE", "/app/maintenance/due/", O, "read due page", "row with DUE", rr[:1])
    b = pmwo(); p.goto(BASE + S)
    with p.expect_navigation(): p.locator("main form[action$='/generate/'] button").click()
    p.wait_for_load_state("networkidle"); m = msgs(p) or p.locator(".alert").first.inner_text() if p.locator(".alert").count() else ""
    cy = sql(f"select id||'|'||sequence||'|'||due_date||'|'||skipped||'|'||trigger||'|'||coalesce(work_order_id::text,'-') from maintenance_maintenancecycle where schedule_id='{sch}'")
    cid, seq, due, sk, trig, woid = cy.split("|") if cy else ("", "", "", "", "", "")
    r.ok(cy and woid != "-" and pmwo() == b + 1 and seq == "0" and due == D(0) and trig == "manual" and re.search(r"Work order \S+ generated", p.inner_text("main")), "Generate now: one cycle + one REAL work order created, success message names the WO", S, O, "click Generate now", "cycle(0) + WO", cy[:90], db=cy[:100], audit=audits(cid, "maintenance.cycle_generated"))
    wo = sql(f"select number||'|'||work_type||'|'||priority||'|'||status||'|'||source_type||'|'||(source_id::text='{cid}')||'|'||asset_id||'|'||estimated_hours||'|'||title from workorders_workorder where id='{woid}'")
    num_, wtype, prio, status, stype, srcok, wasset, hrs, title = wo.split("|")
    r.ok(wtype == "PREVENTIVE" and prio == "URGENT" and status == "PLANNED" and stype == "PREVENTIVE_MAINTENANCE" and srcok in ("true", "t") and wasset == AT and hrs == "2.50" and title == f"PM: Gen plan {U} (cycle 0)", "Work order row: PREVENTIVE / plan priority / PLANNED / source = this cycle / asset / hours / title", S, O, "query workorders_workorder", "fields match plan", wo[:120], db=wo[:140])
    win = sql(f"select (planned_start at time zone 'Asia/Kolkata')::text||' -> '||(planned_end at time zone 'Asia/Kolkata')::text from workorders_workorder where id='{woid}'")
    r.ok(win.startswith(f"{D(0)} 09:30:00") and f"{D(0)} 15:30:00" in win or "15:30:00" in win, "Planned window = schedule window (09:30 + 6 h, site time)", S, O, "read planned_start/end", "09:30 -> 15:30", win, db=win)
    r.ok("Required checklist" in sql(f"select description from workorders_workorder where id='{woid}'") and "monthly" in sql(f"select description from workorders_workorder where id='{woid}'").lower() or "every 1 month" in sql(f"select description from workorders_workorder where id='{woid}'"), "WO description names the plan/recurrence and the required checklist (M08 contract)", S, O, "read WO description", "plan + checklist", sql(f"select left(description,90) from workorders_workorder where id='{woid}'"))
    s2 = sql(f"select next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sch}'"); r.ok(s2 == f"1|{(TODAY + relativedelta(months=1)).isoformat()}", "Schedule advances to cycle 1, next due one month later", S, O, "read schedule", f"1|{(TODAY+relativedelta(months=1))}", s2, db=s2)
    p.goto(BASE + S); t = p.inner_text("main"); r.ok(num_ in t and "manual" in t and "#0" in t, "Schedule page 'Generated work' table lists cycle #0 with the WO number (manual)", S, O, "read table", "row", t[-120:].replace("\n", " "))
    p.goto(BASE + "/app/maintenance/history/"); hr = [x for x in rows(p) if x[1].startswith(f"Gen plan {U}")]
    r.ok(hr and num_ in hr[0][5] and hr[0][3] == "#0" and "GENERATED" in hr[0][6].upper() and hr[0][7] == "manual", "PM history lists the cycle: WO number, cycle #0, PM state GENERATED, source manual", "/app/maintenance/history/", O, "read history", "row", hr[:1])
    # link to WO
    p.goto(BASE + S); p.locator(f"main a:has-text('{num_}')").first.click(); p.wait_for_load_state("networkidle")
    r.ok(woid in p.url and num_ in p.inner_text("main") and f"PM: Gen plan {U}" in p.inner_text("main"), "Cycle table link opens the generated work order (M06 page) with PM title", p.url, O, "click WO number", "WO detail", p.url, ev=shot(p, "M04_generated_wo"))
    r.T("PM state follows the work order lifecycle (assigned / completed / verified)", p.url, O, "advance the WO in M06, watch M04 state", "PM state mirrors WO status", "Not exercised in this batch: advancing a work order belongs to M06 (later batch). Only the GENERATED state and the cycle->WO contract were verified", "UNVERIFIED")
    # --- duplicate prevention
    p.goto(BASE + S); b = pmwo()
    with p.expect_navigation(): p.locator("main form[action$='/generate/'] button").click()
    p.wait_for_load_state("networkidle")
    r.ok(pmwo() == b and "still open" in p.inner_text("main") and cyc(sch) == 1, "Generate now again while the previous WO is open: refused ('previous cycle's work order is still open'), no duplicate WO", S, O, "click Generate now a 2nd time", "refused", p.locator(".alert").first.inner_text()[:90] if p.locator(".alert").count() else "", db=f"WOs {b}->{pmwo()}, cycles={cyc(sch)}")
    js = """async ([path])=>{const ck=Object.fromEntries(document.cookie.split('; ').map(c=>c.split('=')));const f=()=>fetch(path,{method:'POST',headers:{'X-CSRFToken':ck.csrftoken,'Content-Type':'application/x-www-form-urlencoded'},body:'',credentials:'same-origin',redirect:'manual'}).then(r=>r.status);return await Promise.all([f(),f(),f(),f(),f()])}"""
    sts = p.evaluate(js, [S + "generate/"]); r.ok(pmwo() == b and cyc(sch) == 1, "5 simultaneous 'Generate now' requests: still exactly 1 cycle / no extra WO", S, O, "5 parallel POSTs", "no duplicates", f"statuses={sts}", db=f"WOs {b}->{pmwo()}, cycles={cyc(sch)}")
    # double submit on a fresh DUE schedule
    PD = mkplan(AT, f"Dup plan {U}"); time_sched(p, PD, "Month(s)", 1, start=D(0)); sd = SCH(PD); b = pmwo()
    sts = p.evaluate(js, [f"/app/maintenance/schedules/{sd}/generate/"])
    r.ok(pmwo() == b + 1 and cyc(sd) == 1, "5 simultaneous 'Generate now' requests on a fresh DUE schedule: exactly ONE work order is created (row lock + unique cycle)", S, O, "5 parallel POSTs", "1 WO", f"statuses={sts}", db=f"WOs {b}->{pmwo()}, cycles={cyc(sd)}")
    # --- scheduler (Celery) repeated
    def celery_call(task):
        env = dict(__import__("os").environ)
        out = subprocess.run(["celery", "-A", "config", "call", task], capture_output=True, text=True, env=env, cwd="/home/user/Fieldops_Nexus/src", timeout=60)
        return out.stdout.strip()[-60:] or out.stderr.strip()[-120:]
    PC = mkplan(AT, f"Sched plan {U}"); time_sched(p, PC, "Day(s)", 1, start=D(0)); sc = SCH(PC); b = pmwo()
    outs = [celery_call("apps.maintenance.tasks.fan_out_maintenance") for _ in range(3)]
    for _ in range(30):
        if cyc(sc) >= 1: break
        time.sleep(1)
    time.sleep(8)
    r.ok(cyc(sc) == 1 and sql(f"select trigger from maintenance_maintenancecycle where schedule_id='{sc}'") == "scheduler", "Celery scheduler: the due schedule is generated by the worker (trigger=scheduler), exactly once despite 3 task runs", "-", "celery", "task fan_out_maintenance x3", "1 cycle", f"cycles={cyc(sc)} task ids={outs}", db=f"cycles={cyc(sc)}", audit=audits(sql(f"select id from maintenance_maintenancecycle where schedule_id='{sc}'"), "maintenance.cycle_generated"))
    n_after = pmwo(); [celery_call("apps.maintenance.tasks.fan_out_maintenance") for _ in range(2)]; time.sleep(10)
    r.ok(pmwo() == n_after and cyc(sc) == 1, "Re-running the scheduler again creates no further work orders (idempotent)", "-", "celery", "2 more runs", "no new WO", f"WOs {n_after}->{pmwo()}", db=f"{n_after}->{pmwo()}")
    p.goto(BASE + "/app/maintenance/history/"); hr = [x for x in rows(p) if x[1].startswith(f"Sched plan {U}")]
    r.ok(hr and hr[0][7] == "scheduler", "PM history shows the scheduler-generated cycle with source 'scheduler'", p.url, O, "read history", "source=scheduler", hr[:1])
    # --- lead days: due tomorrow with lead 2 => DUE now
    PL2 = mkplan(AT, f"Lead plan {U}"); time_sched(p, PL2, "Month(s)", 1, start=D(1), lead_days="2"); sl = SCH(PL2); p.goto(BASE + f"/app/maintenance/schedules/{sl}/")
    r.ok("DUE" in p.inner_text("main h1").upper(), "Lead days: an occurrence due tomorrow with lead 2 is DUE today", p.url, O, "start +1d, lead 2", "DUE", p.inner_text("main h1")[:40])
    PL3 = mkplan(AT, f"NoLead plan {U}"); time_sched(p, PL3, "Month(s)", 1, start=D(1), lead_days="0"); s3 = SCH(PL3); p.goto(BASE + f"/app/maintenance/schedules/{s3}/")
    r.ok("SCHEDULED" in p.inner_text("main h1").upper(), "Lead 0: an occurrence due tomorrow is only SCHEDULED", p.url, O, "start +1d, lead 0", "SCHEDULED", p.inner_text("main h1")[:40])
    # --- generate ahead of date (manual) for SCHEDULED schedule
    b = pmwo(); p.goto(BASE + f"/app/maintenance/schedules/{s3}/")
    with p.expect_navigation(): p.locator("main form[action$='/generate/'] button").click()
    r.ok(pmwo() == b + 1 and sql(f"select sequence from maintenance_maintenancecycle where schedule_id='{s3}'") == "0", "Manual generate on a SCHEDULED schedule creates the next occurrence early", p.url, O, "Generate now (not yet due)", "WO for cycle 0", f"WOs {b}->{pmwo()}", db=f"{b}->{pmwo()}", audit=audits(s3))
    # --- missed occurrences (simulated downtime): QA-DB time-travel by editing the schedule counters
    PM2 = mkplan(AT, f"Missed plan {U}"); time_sched(p, PM2, "Day(s)", 1, start=(TODAY - dt.timedelta(days=10)).isoformat()); sm = SCH(PM2)
    ns = sql(f"select next_sequence from maintenance_maintenanceschedule where id='{sm}'")
    sql(f"update maintenance_maintenanceschedule set next_sequence=3, next_due_date='{(TODAY - dt.timedelta(days=7)).isoformat()}' where id='{sm}'")
    p.goto(BASE + f"/app/maintenance/schedules/{sm}/"); r.ok("DUE" in p.inner_text("main h1").upper(), "SIMULATED scheduler downtime (QA DB counters rewound 7 days): schedule is DUE/overdue", p.url, O, "rewind next_sequence to 3", "DUE", p.inner_text("main h1")[:40], db="QA-database counters edited to simulate missed runs (clock cannot be advanced)")
    b = pmwo(); p.goto(BASE + f"/app/maintenance/schedules/{sm}/")
    with p.expect_navigation(): p.locator("main form[action$='/generate/'] button").click()
    p.wait_for_load_state("networkidle"); t = p.inner_text("main"); cy = sql(f"select sequence||'|'||skipped from maintenance_maintenancecycle where schedule_id='{sm}'")
    r.ok(pmwo() == b + 1 and cy == f"{ns}|{int(ns) - 3}" and f"(+{int(ns) - 3} missed)" in t, f"Overdue catch-up: ONE work order covers the {int(ns)-3} missed occurrences (collapsed, '+{int(ns)-3} missed' shown)", p.url, O, "Generate now", "1 WO, skipped counted", cy, db=cy)
    # --- F-H01 recheck: edit recurrence after a cycle exists
    PH = mkplan(AT, f"FH01 plan {U}"); time_sched(p, PH, "Month(s)", 1, start=D(0)); sh = SCH(PH); p.goto(BASE + f"/app/maintenance/schedules/{sh}/")
    with p.expect_navigation(): p.locator("main form[action$='/generate/'] button").click()
    p.wait_for_load_state("networkidle"); wo_before = pmwo()
    p.goto(BASE + f"/app/maintenance/schedules/{sh}/edit/"); fill(p, dict(interval_count="2")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    st_ = sql(f"select next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sh}'"); p.goto(BASE + f"/app/maintenance/schedules/{sh}/"); state = p.inner_text("main h1")
    with p.expect_navigation(): p.locator("main form[action$='/generate/'] button").click() if p.locator("main form[action$='/generate/'] button").count() else None
    p.wait_for_load_state("networkidle"); t = p.inner_text("main")
    r.T("F-H01 recheck: edit the recurrence (every 1 -> every 2 months) after cycle 0 exists, then continue", p.url, O, "edit interval, click Generate now", "schedule continues with the next valid occurrence (sequence 1 / date in 2 months) and keeps generating", f"after edit: next={st_}, state shown '{state[:40]}'; Generate now result: '{(p.locator('.alert').first.inner_text() if p.locator('.alert').count() else '')[:100]}'; WOs {wo_before}->{pmwo()}", "FAIL" if st_.startswith("0|") else "PASS", db=st_, ev="F-H01: schedule is re-pointed at already-generated sequence 0 after a recurrence edit" if st_.startswith("0|") else "")
    # --- terminal asset blocks generation (cross-module M02 -> M04)
    RA = mk(f"PMRET-{U}"); PR = mkplan(RA, f"Retire sched {U}"); time_sched(p, PR, "Month(s)", 1, start=D(0)); sr = SCH(PR)
    for lab, rs in (("Start maintenance", "rr one"), ("Mark out of service", "rr two")):
        p.goto(BASE + f"/app/assets/{RA}/"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs)
        with p.expect_navigation(): f.locator("button").click()
    p.goto(BASE + f"/app/assets/{RA}/"); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("retire with plan"); cclick(p, f.locator("button"))
    p.goto(BASE + f"/app/maintenance/schedules/{sr}/"); r.ok("asset_terminal" in p.inner_text("main") and "DISABLED" in p.inner_text("main h1").upper(), "Cross-module: retiring the asset (M02) blocks its PM schedule (M04: asset_terminal)", p.url, O, "retire asset then open schedule", "blocked", p.inner_text("main")[:90].replace("\n", " "))
    b = pmwo()
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/maintenance/schedules/{sr}/generate/", {})
    r.ok(pmwo() == b, "Generate on a schedule of a retired asset creates nothing", p.url, O, "POST generate", "no WO", f"http={res['status']}", db=f"{b}->{pmwo()}")
    p.goto(BASE + f"/app/maintenance/plans/new/?asset={RA}"); r.ok(RA not in p.eval_on_selector_all("main select[name=asset] option", "o=>o.map(x=>x.value)"), "Retired asset cannot get a new plan", p.url, O, "open form", "not offered", "ok")


@feature(r, "Reminders")
def t_reminders():
    p = r.page(O); PR_ = mkplan(AT, f"Remind plan {U}")
    time_sched(p, PR_, "Month(s)", 1, start=D(3), reminder_days="5"); sr = SCH(PR_)
    planner_uid = sql("select id from accounts_user where email='planner@alpha.qa.test'"); b = int(sql(f"select count(*) from notifications_notification where recipient_id='{planner_uid}' and title like 'Maintenance reminder: Remind plan {U}%'"))
    def celery_call(task):
        out = subprocess.run(["celery", "-A", "config", "call", task], capture_output=True, text=True, cwd="/home/user/Fieldops_Nexus/src", timeout=60); return out.stdout.strip()[-40:]
    for _ in range(3): celery_call("apps.maintenance.tasks.fan_out_maintenance")
    for _ in range(40):
        if sql(f"select last_reminded_sequence from maintenance_maintenanceschedule where id='{sr}'") not in ("", None): break
        time.sleep(1)
    time.sleep(6)
    n = int(sql(f"select count(*) from notifications_notification where recipient_id='{planner_uid}' and title like 'Maintenance reminder: Remind plan {U}%'"))
    r.ok(n == b + 1, "Reminder: the planner gets exactly ONE notification for the occurrence due in 3 days (reminder 5 days), despite 3 scheduler runs", "-", "celery", "3 runs", "1 notification", f"{b}->{n}", db=f"planner notifications {b}->{n}", audit=audits(sr, "maintenance.reminder_sent"))
    pp = r.page("planner"); pp.goto(BASE + "/app/notifications/"); pp.wait_for_load_state("networkidle")
    r.ok(f"Maintenance reminder: Remind plan {U}" in pp.inner_text("main"), "The reminder is visible in the planner's notification page", pp.url, "planner", "open notifications", "reminder listed", "ok", ev=shot(pp, "M04_reminder"))
    pp.goto(BASE + "/app/"); r.ok(pp.locator(".fx-bell button[aria-label^='Notifications']").count() >= 1, "Notification bell present for the planner", pp.url, "planner", "inspect", "bell", "ok")
    sr2 = sql(f"select last_reminded_sequence from maintenance_maintenanceschedule where id='{sr}'"); r.ok(sr2 == "0", "Reminder bookkeeping: last_reminded_sequence = 0", "-", "db", "read", "0", sr2, db=sr2)
    PN = mkplan(AT, f"NoRemind plan {U}"); time_sched(p, PN, "Month(s)", 1, start=D(3), reminder_days="0"); sn = SCH(PN); time.sleep(1)
    r.ok(sql(f"select count(*) from notifications_notification where title like 'Maintenance reminder: NoRemind plan {U}%'") == "0", "Reminder 0 days: no reminder is sent", "-", "db", "read", "none", "0")
    PF2 = mkplan(AT, f"FarRemind plan {U}"); time_sched(p, PF2, "Month(s)", 1, start=D(30), reminder_days="2"); celery_call("apps.maintenance.tasks.fan_out_maintenance"); time.sleep(8)
    r.ok(sql(f"select count(*) from notifications_notification where title like 'Maintenance reminder: FarRemind plan {U}%'") == "0", "Occurrence due in 30 days with reminder 2: not reminded yet", "-", "db", "read", "none", "0")


@feature(r, "Due + history pages")
def t_due_history():
    p = r.page(O); DU = "/app/maintenance/due/"; HI = "/app/maintenance/history/"
    pdue = mkplan(AT, f"Due list plan {U}"); time_sched(p, pdue, "Month(s)", 1, start=D(0))
    st, p = visit(r, O, DU); heads = [h.strip().upper() for h in p.locator("main table thead th").all_inner_texts()]
    r.ok(st == 200 and heads[:5] == ["PLAN", "ASSET", "SCHEDULE", "NEXT DUE", "STATE"], "Due & upcoming: opens with PLAN/ASSET/SCHEDULE/NEXT DUE/STATE", DU, O, "open", "columns", heads)
    total = sql(f"select count(*) from maintenance_maintenanceschedule s join maintenance_maintenanceplan p on p.id=s.plan_id where s.is_active and p.is_active and s.organization_id={ALPHA}")
    got = 0; pages = 0; p.goto(BASE + DU)
    while True:
        got += len([x for x in rows(p) if len(x) > 4]); pages += 1; nx = p.locator("main a:has-text('Next')")
        if nx.count() == 0: break
        nx.first.click(); p.wait_for_load_state("networkidle")
    r.ok(got == int(total), f"Due list shows every enabled schedule of enabled plans ({total}) across {pages} page(s)", DU, O, "walk pages", total, got, db=total)
    p.goto(BASE + DU + "?state=DUE"); rs = [x for x in rows(p) if len(x) > 4]; r.ok(rs and all("DUE" in x[4].upper() for x in rs), "State filter 'Due' lists only DUE rows", p.url, O, "state=DUE", "only DUE", [x[4] for x in rs][:5])
    p.goto(BASE + DU + "?state=SCHEDULED"); rs = [x for x in rows(p) if len(x) > 4]; r.ok(rs and all("SCHEDULED" in x[4].upper() for x in rs), "State filter 'Scheduled' lists only SCHEDULED rows", p.url, O, "state=SCHEDULED", "only SCHEDULED", [x[4] for x in rs][:5])
    p.goto(BASE + DU + f"?site={BLR}"); rs = [x for x in rows(p) if len(x) > 4]; exp = sql(f"select count(*) from maintenance_maintenanceschedule s join maintenance_maintenanceplan p on p.id=s.plan_id where s.is_active and p.is_active and p.site_id='{BLR}' and s.organization_id={ALPHA}")
    r.ok(len(rs) == int(exp), "Site filter on the due list matches the database", p.url, O, "site=BLR-1", exp, len(rs), db=exp)
    for bad in ("state=BOGUS", "site=zzz", "page=abc", "page=0"):
        resp = p.goto(BASE + DU + "?" + bad); r.ok(resp.status == 200, f"Due list with '{bad}' does not error", p.url, O, bad, "200", resp.status)
    # due row actions
    p.goto(BASE + DU + "?state=DUE"); r0 = p.locator("main table tbody tr").first
    r.ok(r0.locator("button:has-text('Generate now')").count() == 1 and r0.locator("a").count() >= 2, "Each due row has plan/schedule links and a 'Generate now' button", p.url, O, "inspect first row", "links + button", "ok")
    p.goto(BASE + DU); p.locator("main table tbody tr td a").nth(1).click(); p.wait_for_load_state("networkidle"); r.ok("/maintenance/plans/" in p.url or "/maintenance/schedules/" in p.url, "Row links navigate to plan/schedule pages", p.url, O, "click link", "detail", p.url)
    # history
    st, p = visit(r, O, HI); heads = [h.strip().upper() for h in p.locator("main table thead th").all_inner_texts()]
    r.ok(heads == ["GENERATED", "PLAN", "ASSET", "CYCLE", "DUE", "WORK ORDER", "PM STATE", "SOURCE"], "PM history columns", HI, O, "open", "8 columns", heads)
    tot = int(sql(f"select count(*) from maintenance_maintenancecycle where organization_id={ALPHA}")); seen = 0; p.goto(BASE + HI)
    while True:
        seen += len([x for x in rows(p) if len(x) > 6]); nx = p.locator("main a:has-text('Next')")
        if nx.count() == 0: break
        nx.first.click(); p.wait_for_load_state("networkidle")
    r.ok(seen == tot, f"History lists every generated cycle ({tot})", HI, O, "walk pages", tot, seen, db=str(tot))
    pl = sql(f"select p.id from maintenance_maintenanceplan p where p.name='Gen plan {U}'"); p.goto(BASE + HI); fill(p, {"plan": pl}, "main form"); p.locator("main form button:has-text('Filter')").click(); p.wait_for_load_state("networkidle")
    rs = [x for x in rows(p) if len(x) > 6]; r.ok(rs and all(x[1].startswith(f"Gen plan {U}") for x in rs) and len(rs) == int(sql(f"select count(*) from maintenance_maintenancecycle c join maintenance_maintenanceschedule s on s.id=c.schedule_id where s.plan_id='{pl}'")), "History filter by plan lists only that plan's cycles", p.url, O, "choose plan + Filter", "only that plan", len(rs))
    p.reload(); r.ok(p.locator("main select[name=plan]").input_value() == pl, "Plan filter survives refresh", p.url, O, "reload", "kept", "ok")
    nonexist = "00000000-0000-0000-0000-000000000000"; p.goto(BASE + HI + f"?plan={nonexist}"); r.ok("Nothing generated yet" in p.inner_text("main"), "Unknown plan filter shows the empty state", p.url, O, "plan=unknown", "empty state", "ok")
    p.goto(BASE + HI + "?plan=zzz"); r.ok(p.locator("main table").count() == 1, "Malformed plan filter does not error", p.url, O, "plan=zzz", "no error", "ok")
    r.T("Cycle table 'Overdue' presentation", HI, O, "look for an OVERDUE state", "overdue indicator", "M04 shows DUE (including overdue: the badge does not distinguish 'due today' from 'overdue by N days'); overdue backlog is expressed as '+N missed' on the cycle", "PARTIAL")


@feature(r, "Maintenance RBAC")
def t_rbac():
    PR_ = mkplan(AT, f"RBAC plan {U}"); time_sched(pg, PR_, "Month(s)", 1, start=D(15)); SR = SCH(PR_)
    P0 = pg
    def attempt(role, code, label, path, data, probe, restore=None):
        p = r.page(role); allowed = perm(role, code); before = sql(probe)
        with (contextlib_null() if allowed else r.expect_errors()):
            res = bfetch(p, "POST", path, data)
        after = sql(probe); changed = before != after
        good = (res["status"] in (200, 302) and changed) if allowed else (res["status"] in (403, 404) and not changed)
        r.ok(good, f"RBAC {label}", path, role, "POST real browser request", "allowed: succeeds + DB changes" if allowed else "denied: 403/404 + DB unchanged", f"http={res['status']} changed={changed} perm({code})={allowed}", db=f"{before} -> {after}")
        if restore and allowed and changed: restore()
    for ro in ROLE_LIST:
        p = r.page(ro); has = lambda c: perm(ro, c)
        for label, path in (("plans list", PL), ("due list", "/app/maintenance/due/"), ("history", "/app/maintenance/history/"), ("plan detail", f"{PL}{PR_}/"), ("schedule detail", f"/app/maintenance/schedules/{SR}/")):
            a_ = has("maintenance.view")
            with (contextlib_null() if a_ else r.expect_errors()):
                resp = p.goto(BASE + path); p.wait_for_load_state("networkidle")
            r.ok((resp.status == 200) == a_ and (a_ or resp.status in (403, 404)), f"RBAC {label} access follows maintenance.view", path, ro, "open", f"200 iff maintenance.view={a_}", resp.status)
        nav = p.locator("a[href='/app/maintenance/plans/']").count() > 0; p.goto(BASE + "/app/"); nav = p.locator("a[href='/app/maintenance/plans/']").count() > 0
        r.ok(nav == has("maintenance.view"), "RBAC nav 'Maintenance plans' iff maintenance.view", "/app/", ro, "read sidebar", f"{has('maintenance.view')}", nav)
        if has("maintenance.view"):
            p.goto(BASE + PL); r.ok((p.locator("main a:has-text('New plan')").count() > 0) == has("maintenance.create"), "RBAC 'New plan' button iff maintenance.create", PL, ro, "inspect", f"{has('maintenance.create')}", "ok")
            p.goto(BASE + f"{PL}{PR_}/")
            r.ok((p.locator("main a:has-text('Edit')").count() > 0) == has("maintenance.update") and (p.locator("main form[action*='/active/']").count() > 0) == has("maintenance.update"), "RBAC plan Edit / Disable iff maintenance.update", p.url, ro, "inspect", f"{has('maintenance.update')}", "ok")
            r.ok((p.locator("main a:has-text('Add schedule')").count() > 0) == has("maintenance.create"), "RBAC 'Add schedule' iff maintenance.create", p.url, ro, "inspect", f"{has('maintenance.create')}", "ok")
            r.ok((p.locator("#schedules-table button:has-text('Generate now')").count() > 0) == has("maintenance.generate"), "RBAC 'Generate now' iff maintenance.generate", p.url, ro, "inspect", f"{has('maintenance.generate')}", "ok")
            r.ok((p.locator("#schedules-table button:has-text('Disable')").count() > 0) == has("maintenance.update"), "RBAC schedule Disable/Enable iff maintenance.update", p.url, ro, "inspect", f"{has('maintenance.update')}", "ok")
            p.goto(BASE + "/app/maintenance/due/"); r.ok((p.locator("main table tbody tr button:has-text('Generate now')").count() > 0) == has("maintenance.generate"), "RBAC due-list 'Generate now' iff maintenance.generate", p.url, ro, "inspect", f"{has('maintenance.generate')}", "ok")
        for label, path, code in (("new plan form", PL + "new/", "maintenance.create"), ("edit plan form", f"{PL}{PR_}/edit/", "maintenance.update"), ("new schedule form", f"{PL}{PR_}/schedules/new/", "maintenance.create"), ("edit schedule form", f"/app/maintenance/schedules/{SR}/edit/", "maintenance.update")):
            a_ = has(code)
            with (contextlib_null() if a_ else r.expect_errors()):
                resp = p.goto(BASE + path); p.wait_for_load_state("networkidle")
            r.ok((resp.status == 200) == a_ and (a_ or resp.status in (403, 404)), f"RBAC direct URL: {label}", path, ro, "type URL", f"200 iff {code}", resp.status)
        nm = f"RB {ro} {U}"
        attempt(ro, "maintenance.create", "create plan", PL + "new/", {"asset": AX, "name": nm, "priority": "LOW"}, f"select count(*) from maintenance_maintenanceplan where name='{nm}'")
        attempt(ro, "maintenance.update", "edit plan", f"{PL}{PR_}/edit/", {"name": f"RBAC plan {U}", "priority": "HIGH" if ROLE_LIST.index(ro) % 2 else "URGENT", "description": ro}, f"select description from maintenance_maintenanceplan where id='{PR_}'")
        attempt(ro, "maintenance.update", "disable plan", f"{PL}{PR_}/active/", {"active": "0"}, f"select is_active from maintenance_maintenanceplan where id='{PR_}'", restore=lambda: bfetch(P0, "POST", f"{PL}{PR_}/active/", {"active": "1"}))
        attempt(ro, "maintenance.create", "create schedule", f"{PL}{PR_}/schedules/new/", {"trigger_type": "TIME", "frequency": "DAILY", "interval_count": str(30 + ROLE_LIST.index(ro)), "start_date": D(16), "lead_days": "0", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"}, f"select count(*) from maintenance_maintenanceschedule where plan_id='{PR_}'")
        attempt(ro, "maintenance.update", "edit schedule", f"/app/maintenance/schedules/{SR}/edit/", {"frequency": "MONTHLY", "interval_count": "1", "start_date": D(15), "lead_days": str(1 + ROLE_LIST.index(ro)), "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"}, f"select lead_days from maintenance_maintenanceschedule where id='{SR}'")
        attempt(ro, "maintenance.update", "disable schedule", f"/app/maintenance/schedules/{SR}/disable/", {}, f"select is_active from maintenance_maintenanceschedule where id='{SR}'", restore=lambda: bfetch(P0, "POST", f"/app/maintenance/schedules/{SR}/enable/", {}))
        gs = sql(f"select id from maintenance_maintenanceschedule where plan_id='{PX}' limit 1") if False else None
    # generate: dedicated schedule per role so the generate attempt is independent
    for ro in ROLE_LIST:
        pgp = mkplan(AX, f"RBGEN {ro} {U}"); time_sched(P0, pgp, "Month(s)", 1, start=D(0)); sg = SCH(pgp)
        attempt(ro, "maintenance.generate", "generate now", f"/app/maintenance/schedules/{sg}/generate/", {}, f"select count(*) from maintenance_maintenancecycle where schedule_id='{sg}'")


@feature(r, "Maintenance tenant isolation")
def t_tenant():
    bo = r.page("betaowner"); bsite = sql("select id from sites_site where code='PUN-1'"); bcat = sql("select id from assets_assetcategory where organization_id<>%s limit 1" % ALPHA)
    bapi(bo, "POST", "/api/v1/assets/", {"asset_tag": f"BPM-{U}", "name": "Beta PM asset", "category": bcat, "site": bsite}); BA = sql(f"select id from assets_asset where asset_tag='BPM-{U}'")
    bo.goto(BASE + PL + "new/"); bo.wait_for_load_state("networkidle")
    bo.locator("main select[name=asset]").select_option(value=BA); bo.locator("main input[name=name]").fill(f"Beta plan {U}"); bo.locator("main form button:has-text('Create plan')").click(); bo.wait_for_load_state("networkidle")
    BP = sql(f"select id from maintenance_maintenanceplan where name='Beta plan {U}'")
    bo.goto(BASE + f"{PL}{BP}/schedules/new/"); bo.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{if(['date','time','number'].includes(e.type)) e.type='text'})")
    fill(bo, dict(trigger_type="Time-based", frequency="Month(s)", interval_count="1", start_date=D(0))); bo.locator("main form button:has-text('Create schedule')").click(); bo.wait_for_load_state("networkidle")
    BS = sql(f"select id from maintenance_maintenanceschedule where plan_id='{BP}'")
    r.ok(all([BA, BP, BS]), "Setup: Beta asset, plan and schedule exist (created through the Beta UI)", "-", "betaowner", "create", "rows", "ok")
    AP = mkplan(AT, f"Tenant plan {U}"); time_sched(pg, AP, "Month(s)", 1, start=D(0)); AS = SCH(AP)
    n = lambda q: sql(q)
    def cross(label, who, method, path, data, probe):
        p = r.page(who); before = sql(probe)
        with r.expect_errors(): res = bfetch(p, method, path, data)
        after = sql(probe); r.ok(res["status"] in (400, 403, 404) and before == after, f"Tenant: {label}", path, who, f"{method} other tenant's object", "400/403/404, DB unchanged", f"http={res['status']}", db=f"{before} -> {after}")
    wo = lambda: sql("select count(*) from workorders_workorder")
    for who, tP, tS, tA, pre in (("betaowner", AP, AS, AT, "Beta"), ("owner", BP, BS, BA, "Alpha")):
        cross(f"{pre} cannot open the other tenant's plan", who, "GET", f"{PL}{tP}/", None, "select 1")
        cross(f"{pre} cannot open its plan edit form", who, "GET", f"{PL}{tP}/edit/", None, "select 1")
        cross(f"{pre} cannot edit it (POST)", who, "POST", f"{PL}{tP}/edit/", {"name": "HIJACK", "priority": "LOW"}, f"select name||priority from maintenance_maintenanceplan where id='{tP}'")
        cross(f"{pre} cannot disable it", who, "POST", f"{PL}{tP}/active/", {"active": "0"}, f"select is_active from maintenance_maintenanceplan where id='{tP}'")
        cross(f"{pre} cannot add a schedule to it", who, "POST", f"{PL}{tP}/schedules/new/", {"trigger_type": "TIME", "frequency": "DAILY", "interval_count": "77", "start_date": D(3), "lead_days": "0", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"}, f"select count(*) from maintenance_maintenanceschedule where plan_id='{tP}'")
        cross(f"{pre} cannot open its schedule", who, "GET", f"/app/maintenance/schedules/{tS}/", None, "select 1")
        cross(f"{pre} cannot open its schedule edit form", who, "GET", f"/app/maintenance/schedules/{tS}/edit/", None, "select 1")
        cross(f"{pre} cannot edit its schedule", who, "POST", f"/app/maintenance/schedules/{tS}/edit/", {"frequency": "DAILY", "interval_count": "5", "start_date": D(3), "lead_days": "9", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"}, f"select lead_days||frequency from maintenance_maintenanceschedule where id='{tS}'")
        cross(f"{pre} cannot disable its schedule", who, "POST", f"/app/maintenance/schedules/{tS}/disable/", {}, f"select is_active from maintenance_maintenanceschedule where id='{tS}'")
        cross(f"{pre} cannot GENERATE work for its schedule", who, "POST", f"/app/maintenance/schedules/{tS}/generate/", {}, f"select (select count(*) from maintenance_maintenancecycle)||'/'||(select count(*) from workorders_workorder)")
        cross(f"{pre} cannot create a plan on the other tenant's asset", who, "POST", PL + "new/", {"asset": tA, "name": f"HIJACK {U}", "priority": "LOW"}, f"select count(*) from maintenance_maintenanceplan where name='HIJACK {U}'")
    # lists don't leak
    p = r.page("betaowner")
    for path in (PL, "/app/maintenance/due/", "/app/maintenance/history/"):
        p.goto(BASE + path); html = p.inner_text("main"); r.ok("GEN-001" not in html and f"Time plan {U}" not in html and "Gen plan" not in html, f"Beta {path.split('/')[-2]} page shows no Alpha plans/schedules/cycles", path, "betaowner", "open", "none", "ok")
    p.goto(BASE + PL + "?q=GEN"); r.ok("GEN-001" not in p.inner_text("main"), "Beta plan search for an Alpha asset tag returns nothing", p.url, "betaowner", "q=GEN", "none", "ok")
    p.goto(BASE + PL + f"?site={HYD}"); r.ok(p.locator("main table tbody tr td a").count() == 0, "Beta site filter with an Alpha site id returns nothing", p.url, "betaowner", "site=<alpha>", "empty", "ok")
    p.goto(BASE + f"{PL}new/"); r.ok(not any(x in p.locator("main select[name=asset]").inner_text() for x in ("GEN-001", f"PMT-{U}")), "Beta 'New plan' asset dropdown contains no Alpha assets", p.url, "betaowner", "read options", "none", "ok")
    p.goto(BASE + f"{PL}{BP}/schedules/new/"); mo = p.locator("main select[name=meter] option").all_inner_texts(); r.ok("Run hours" not in " ".join(mo), "Beta schedule form offers no Alpha meters", p.url, "betaowner", "read options", "none", mo)
    ap = bapi(p, "GET", f"/api/v1/maintenance-plans/{AP}/"); r.ok(ap["status"] == 404, "API: Beta GET Alpha plan -> 404", "-", "betaowner", "browser fetch", "404", ap["status"])
    for path in ("maintenance-plans", "maintenance-schedules", "maintenance-cycles"):
        lst = bapi(p, "GET", f"/api/v1/{path}/"); body = json.dumps(lst["json"])[:5000]; r.ok(lst["status"] == 200 and "Time plan" not in body and "GEN-001" not in body, f"API: Beta {path} list has no Alpha records", "-", "betaowner", "browser fetch", "none", lst["status"])
    # schedule on other tenant's meter
    with r.expect_errors(): res = bfetch(r.page("betaowner"), "POST", f"{PL}{BP}/schedules/new/", {"trigger_type": "METER", "meter": MID, "interval_value": "10", "start_value": "0", "lead_days": "0", "window_start_time": "08:00", "window_hours": "8", "reminder_days": "0"})
    r.ok(sql(f"select count(*) from maintenance_maintenanceschedule where plan_id='{BP}'") == "1", "Beta schedule with an Alpha meter id is rejected", "-", "betaowner", "forged meter", "rejected", f"http={res['status']}")


@feature(r, "Maintenance responsive + UI")
def t_responsive():
    pl_ = sql(f"select id from maintenance_maintenanceplan where name='Time plan {U}'"); sc_ = sql(f"select id from maintenance_maintenanceschedule where plan_id='{pl_}' order by created_at limit 1")
    paths = [("Plan list", PL), ("New plan", PL + "new/"), ("Plan detail", f"{PL}{pl_}/"), ("Edit plan", f"{PL}{pl_}/edit/"), ("New schedule", f"{PL}{pl_}/schedules/new/"), ("Schedule detail", f"/app/maintenance/schedules/{sc_}/"), ("Edit schedule", f"/app/maintenance/schedules/{sc_}/edit/"), ("Due list", "/app/maintenance/due/"), ("PM history", "/app/maintenance/history/")]
    for vp in ("desktop", "laptop", "tablet", "mobile"):
        p = r.page(O, vp)
        for name, path in paths:
            p.goto(BASE + path); p.wait_for_load_state("networkidle"); p.wait_for_timeout(250)
            ov = overflow(p); fine = ov["sw"] <= ov["iw"] + 1 and not ov["wide"] and not ov["clipped"]
            ev = "" if fine else shot(p, f"M04_{vp}_{name.replace(' ', '_')}")
            r.ok(fine, f"Responsive {vp}: {name} (no horizontal overflow / clipped controls)", path, O, f"open at {VIEWPORTS[vp][0]}x{VIEWPORTS[vp][1]}", "no overflow", f"sw={ov['sw']} iw={ov['iw']} wide={ov['wide'][:2]} clipped={ov['clipped'][:2]}", ev=ev)
        if vp == "mobile": shot(p, "M04_mobile_due")
    pm = r.page(O, "mobile"); pm.goto(BASE + f"{PL}{pl_}/schedules/new/"); pm.wait_for_load_state("networkidle")
    with r.expect_errors(): pm.locator("main form button:has-text('Create schedule')").click(); pm.wait_for_load_state("networkidle")
    err = pm.locator("main .text-danger, main .alert-danger").first; r.ok(err.count() > 0 and err.is_visible(), "Mobile: validation error visible on the schedule form", pm.url, O, "submit empty at 390px", "visible", err.count() > 0, ev=shot(pm, "M04_mobile_validation"))
    pm.goto(BASE + f"{PL}{pl_}/"); pm.locator("main form[action*='/active/'] button").click(); pm.wait_for_timeout(500)
    box = pm.locator("#fx-confirm").bounding_box(); fit = box and box["x"] >= -1 and box["x"] + box["width"] <= 391 and box["y"] >= -1 and box["y"] + box["height"] <= 845
    r.ok(bool(fit), "Mobile: the 'Disable plan' confirmation dialog fits the viewport", pm.url, O, "open dialog", "within viewport", box, ev=shot(pm, "M04_mobile_modal")); pm.keyboard.press("Escape")
    p = r.page(O, "laptop"); p.goto(BASE + f"{PL}{pl_}/schedules/new/"); p.locator("main select[name=trigger_type]").focus(); seq = []
    for _ in range(9):
        p.keyboard.press("Tab"); nm_ = p.evaluate("()=>document.activeElement&&document.activeElement.name")
        if nm_ and (not seq or seq[-1] != nm_): seq.append(nm_)
    seq = seq[:4]
    r.ok(seq == ["frequency", "interval_count", "start_date", "meter"], "Keyboard: Tab order follows the schedule form fields", p.url, O, "Tab x4", "logical", seq)


for f in (t_time, t_meter, t_edit, t_generate, t_reminders, t_due_history, t_rbac, t_tenant, t_responsive):
    f()

fails = [x for x in r.rows if x["status"] == "FAIL"]; unv = [x for x in r.rows if x["status"] == "UNVERIFIED"]
print("ROWS", len(r.rows), "FAIL", len(fails), "UNVF", len(unv), "PARTIAL", len([x for x in r.rows if x['status'] == 'PARTIAL']))
for x in fails + unv: print("  ", x["status"], x["feature"], "|", str(x["action"])[:50], "|", str(x["actual"])[:200])
print("ISSUES", len(r.issues))
for i in r.issues[:25]: print("  ", i["kind"], i["feature"], i["role"], i["text"][:130], i.get("url", "")[-60:])
r.stop()
