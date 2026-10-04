import django; django.setup()
from datetime import date, datetime, timedelta, UTC
from django.utils import timezone
from apps.tenancy.models import Organization
from apps.core.tenant import tenant_context
from apps.assets.models import Asset
from apps.maintenance import services as pm
from apps.maintenance.models import MaintenanceCycle
from django.contrib.auth import get_user_model
org=Organization.objects.get(slug="alpha-field-services"); U=get_user_model().objects.get(email="owner@alpha.qa.test")
clock={"now":datetime(2026,1,8,6,0,tzinfo=UTC)}
real_now=timezone.now; timezone.now=lambda: clock["now"]
with tenant_context(org):
    asset=Asset.objects.get(asset_tag="HVAC-001")
    plan=pm.create_plan(org,asset=asset,name="BUGPROBE weekly->biweekly",actor=U)
    sch=pm.create_schedule(plan,actor=U,trigger_type="TIME",frequency="WEEKLY",interval_count=1,start_date=date(2026,1,1))
    gen=[]
    for wk in range(8):  # 8 weekly runs
        r=pm.run_for_organization(org,now=clock["now"]); gen.append(r["generated"]); clock["now"]+=timedelta(days=7)
    seqs=list(MaintenanceCycle.objects.filter(schedule=sch).order_by("sequence").values_list("sequence",flat=True))
    print("weekly generation per run:",gen,"cycle sequences:",seqs)
    sch.refresh_from_db(); print("before edit next_sequence",sch.next_sequence,sch.next_due_date,"now",clock["now"].date())
    pm.update_schedule(sch,actor=U,interval_count=2)
    sch.refresh_from_db(); print("after edit  next_sequence",sch.next_sequence,sch.next_due_date)
    gen2=[]; 
    for d in range(10):  # 10 more weeks, biweekly schedule -> expect a WO about every 2 weeks (5)
        r=pm.run_for_organization(org,now=clock["now"]); gen2.append(r["generated"]); clock["now"]+=timedelta(days=7)
    sch.refresh_from_db()
    print("generation per week after edit:",gen2,"total new WOs:",sum(gen2),"expected ~5; last_error=",repr(sch.last_error),"next_sequence",sch.next_sequence)
    print("cycles now:",list(MaintenanceCycle.objects.filter(schedule=sch).order_by("sequence").values_list("sequence",flat=True)))
timezone.now=real_now
