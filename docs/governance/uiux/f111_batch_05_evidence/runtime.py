"""BATCH-05 bounded Development preparation and real HTTP security matrix."""
import hashlib
import json
import re
import html
import runpy
import subprocess
import sys
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
support=runpy.run_path(str(OUT.parent/"f111_batch_04_evidence/runtime.py"),run_name="batch05_support")
snapshot=support["snapshot"]
row_hashes=support["row_hashes"]
digest=support["support"]["digest"]
class Parsed(support["Parsed"]):
 def __init__(self,body):
  super().__init__(body)
  self.errors += [html.unescape(re.sub(r"<[^>]+>"," ",m)).strip() for m in re.findall(r'<div[^>]*role="alert"[^>]*>(.*?)</div>',body,re.S)]

def observation_snapshot():
 from django.apps import apps
 result={}
 for label in ("inventory.StockTransaction","inventory.Warehouse","procurement.GoodsReceipt","procurement.GoodsReceiptItem","audit.AuditEvent","sessions.Session"):
  model=apps.get_model(label);rows=list(model._base_manager.order_by("pk").values_list(*[f.attname for f in model._meta.concrete_fields]))
  result[label]={"count":len(rows),"sha256":digest(rows)}
 return result

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from apps.accounts.models import User
from apps.audit.models import AuditEvent,AuditAction
from apps.inventory.forms import StockTransactionForm
from apps.inventory.models import Warehouse,StockTransaction
from apps.inventory.services import create_warehouse,create_stock_transaction
from apps.organizations.models import Organization,OrganizationMembership
from apps.organizations.authorization import has_business_permission,get_active_membership
from apps.procurement.models import PurchaseOrder,GoodsReceiptItem
from apps.procurement.services import (create_purchase_order,add_purchase_order_item,issue_purchase_order,
 create_goods_receipt,add_goods_receipt_item,post_goods_receipt)
from apps.projects.models import Project

BASE="http://localhost:8008"
PATH="/inventory/transactions/create/"
ALIASES=("uiux.persona.project-manager","uiux.persona.tenant-admin","uiux.reference.batch03.site-only")
CODES=dict(zip("ABCDX",["PRJ-01-01","PRJ-01-02","PRJ-01-03","PRJ-01-04","PRJ-02-01"],strict=True))
FIELDS=("project","source_warehouse","destination_warehouse","goods_receipt_item")

def save(name,data):
 (OUT/name).write_text(json.dumps(data,default=str,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def guard():
 assert settings.SETTINGS_MODULE=="config.settings.development" and settings.DEBUG
 assert connection.vendor=="postgresql" and connection.settings_dict["NAME"]=="construction_erp"
 assert connection.settings_dict["HOST"] in {"localhost","127.0.0.1","::1"}
 assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
 with connection.cursor() as c:c.execute("SET default_transaction_read_only = off")

def authority():
 rows=support["authority"]()
 for a in rows:
  org=Organization.objects.get(slug=a["organization"])
  a["stock_create"]=has_business_permission(user=User.objects.get(username=a["actor"]),organization=org,permission="stock_transactions.create",allow_any_scope=True)
 return rows

def sources():
 return {key:{"project":Project.objects.get(code=code),
  "warehouse":Warehouse.objects.get(project__code=code,code="WH-"+("01" if key=="X" else f"0{ord(key)-64}"),is_active=True,archived_at__isnull=True),
  "item":GoodsReceiptItem.objects.select_related("goods_receipt__project","material__unit_of_measure").get(goods_receipt__receipt_number="B05-RUNTIME-GR-"+key)} for key,code in CODES.items()}

def prepare():
 guard();before=authority();save("PREPARATION_BEFORE.json",{"models":snapshot(),"rows":row_hashes(),"authority":before})
 assert all(a["stock_create"] and not a["staff"] and not a["superuser"] for a in before)
 assert [g["scope_type"] for a in before if a["actor"]==ALIASES[2] for g in a["grants"]]==["site"]
 assert not GoodsReceiptItem.objects.filter(goods_receipt__status="posted",stock_transactions__isnull=True).exists()
 assert not PurchaseOrder.objects.filter(order_number__startswith="B05-RUNTIME").exists()
 created=[]
 with transaction.atomic():
  for key,code in CODES.items():
   source=PurchaseOrder.objects.select_related("project","supplier","organization").get(order_number__startswith="POR-",project__code=code)
   org=source.organization;actor=User.objects.get(username=f"account.{org.slug}.owner");material=source.items.select_related("material").first().material
   order=create_purchase_order(organization=org,actor=actor,project=source.project,supplier=source.supplier,
    order_number="B05-RUNTIME-PO-"+key,order_date=source.order_date,notes="Synthetic Development BATCH-05 source control")
   item=add_purchase_order_item(organization=org,actor=actor,purchase_order=order,material=material,quantity=Decimal(2),unit_price=Decimal(1))
   order=issue_purchase_order(organization=org,actor=actor,purchase_order=order)
   receipt=create_goods_receipt(organization=org,actor=actor,purchase_order=order,receipt_number="B05-RUNTIME-GR-"+key,received_at=timezone.now(),notes="Synthetic Development-only selector control; no stock posting")
   line=add_goods_receipt_item(organization=org,actor=actor,goods_receipt=receipt,purchase_order_item=item,quantity=Decimal(1))
   receipt=post_goods_receipt(organization=org,actor=actor,goods_receipt=receipt)
   assert receipt.status=="posted"
   created.append({"key":key,"actor":actor.username,"project":code,"order":order.pk,"version":order.current_version_id,"receipt":receipt.pk,"item":line.pk,"label":str(line),"status":receipt.status})
  org=Organization.objects.get(slug="demo-construction-01");owner=User.objects.get(username=f"account.{org.slug}.owner")
  for code,name,project in (("B05-CENTRAL","B05 synthetic central",None),("B05-SECOND-B","B05 synthetic second B",Project.objects.get(code=CODES["B"]))):
   assert not Warehouse.objects.filter(organization=org,code=code).exists()
   w=create_warehouse(organization=org,actor=owner,code=code,name=name,project=project)
   created.append({"warehouse":w.pk,"code":code,"actor":owner.username})
 assert before==authority()
 save("FIXTURES.json",{"created":created,"authority_before":before,"authority_after":authority(),"temporary_authority":"NONE"})
 save("RUNTIME_BEFORE.json",{"models":snapshot(),"rows":row_hashes(),"authority":authority(),"database":connection.settings_dict["NAME"],"settings":settings.SETTINGS_MODULE,"pending_migrations":0})
 print("Canonical preparation PASS: five posted receipt sources; two warehouses; authority unchanged")

def payload(kind="receipt",key="B"):
 src=sources();r=src[key]
 return dict(transaction_number="B05-RUNTIME-"+kind.upper(),transaction_type=kind,project=str(r["project"].pk),
  material=str(src["B"]["item"].material_id),quantity="1",occurred_at="2026-10-22T10:00",reference="",notes="Synthetic Development runtime control",
  source_warehouse=str(r["warehouse"].pk) if kind in ("issue","transfer","adjustment_out") else "",
  destination_warehouse=str(Warehouse.objects.get(code="B05-SECOND-B").pk if kind=="transfer" and key=="B" else r["warehouse"].pk) if kind in ("receipt","transfer","adjustment_in") else "",
  goods_receipt_item=str(r["item"].pk) if kind=="receipt" else "")

def login(alias):
 opener=build_opener(HTTPCookieProcessor(CookieJar()))
 def request(path,data=None):
  req=Request(BASE+path,data=None if data is None else urlencode(data).encode(),headers={"Referer":BASE+path})
  try:response=opener.open(req,timeout=30)
  except HTTPError as exc:response=exc
  return response.status,response.read().decode(),response.geturl()
 _,body,_=request("/accounts/login/")
 command="$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/"+alias+".clixml'); $c.GetNetworkCredential().Password"
 secret=subprocess.run([r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe","-NoProfile","-Command",command],capture_output=True,text=True,check=True).stdout.strip()
 status,body,url=request("/accounts/login/",{"username":alias,"password":secret,"csrfmiddlewaretoken":Parsed(body).token});del secret
 assert status==200 and "/accounts/login/" not in url and alias in body
 return request

def http():
 guard();records=[];src=sources();org=Organization.objects.get(slug="demo-construction-01")
 for alias,allowed in zip(ALIASES,("AB","ABCD",""),strict=True):
  request=login(alias);actor=User.objects.get(username=alias);member=get_active_membership(user=actor,organization=org)
  def observe(label,data=None):
   before=observation_snapshot();audit_before=set(AuditEvent.objects.values_list("pk",flat=True));status,body,url=request(PATH,data);parsed=Parsed(body)
   form=StockTransactionForm(organization=org,membership=member)
   expected={f:[{"value":str(v),"label":str(l)} for v,l in form.fields[f].choices] for f in FIELDS}
   actual={f:parsed.fields[f] for f in FIELDS}
   leaks=[]
   shared_labels={str(t) for k,r in src.items() if k in allowed for t in (str(r["warehouse"]),r["warehouse"].name,r["project"].name)}
   if not allowed:shared_labels.add(src["A"]["project"].name)
   for key,r in src.items():
    if key in allowed:continue
    # Site-parent context appears in the existing navigation; it grants no movement choices.
    tokens=[r["warehouse"].pk,str(r["warehouse"]),r["warehouse"].name,r["item"].pk,str(r["item"]),r["item"].goods_receipt.receipt_number]
    if not (not allowed and key=="A"):tokens += [r["project"].pk,r["project"].name]
    leaks += [str(t) for t in tokens if str(t) in body and str(t) not in shared_labels]
   deltas=[n for n,v in observation_snapshot().items() if before[n]!=v]
   new_audits=list(AuditEvent.objects.exclude(pk__in=audit_before).values("action","actor__username","entity_id"))
   assert all(a["action"]==AuditAction.STOCK_RECEIPT_FAILED and a["actor__username"]==ALIASES[0] and str(a["entity_id"])==str(src["B"]["item"].pk) for a in new_audits),new_audits
   record={"failure_audits":new_audits,"actor":alias,"label":label,"method":"POST" if data else "GET","status":status,"options":actual,"errors":parsed.errors,"forbidden_metadata":leaks,"model_deltas":deltas,"response_sha256":hashlib.sha256(body.encode()).hexdigest(),"real_authentication_csrf":True}
   records.append(record);save("RUNTIME_HTTP.json",records)
   assert status==200 and url==BASE+PATH and not leaks and actual==expected and set(deltas)<={"sessions.Session","audit.AuditEvent"},record
   for field,slot in (("project","project"),("source_warehouse","warehouse"),("destination_warehouse","warehouse"),("goods_receipt_item","item")):
    values={o["value"] for o in actual[field]}
    assert all((str(r[slot].pk) in values)==(k in allowed) for k,r in src.items())
   central=str(Warehouse.objects.get(code="B05-CENTRAL").pk)
   assert all((central in {o["value"] for o in actual[f]})==(allowed=="ABCD") for f in ("source_warehouse","destination_warehouse"))
   return parsed
  parsed=observe("GET")
  if allowed=="ABCD":continue
  for key in "CDX" if allowed else "ABCDX":
   for kind,field,slot in (("issue","project","project"),("issue","source_warehouse","warehouse"),("transfer","destination_warehouse","warehouse"),("receipt","goods_receipt_item","item")):
    data=payload(kind);data[field]=str(src[key][slot].pk)
    form=StockTransactionForm(data,organization=org,membership=member);assert not form.is_valid() and field in form.errors
    parsed=observe("forced "+key+" "+field,data|{"csrfmiddlewaretoken":parsed.token});assert parsed.errors
  for kind in ("receipt","transfer"):
   data=payload(kind);data.pop("transaction_number")
   parsed=observe(kind+" missing-required redisplay",data|{"csrfmiddlewaretoken":parsed.token});assert parsed.errors
  if allowed:
   for kind in ("receipt","transfer"):
    data=payload(kind);data["destination_warehouse"]=str(src["A"]["warehouse"].pk)
    parsed=observe(kind+" incompatible authorized Projects service rejection",data|{"csrfmiddlewaretoken":parsed.token});assert parsed.errors
 save("HTTP_SUMMARY.json",{"observations":len(records),"all_pass":True,"same_tenant_cross_tenant_site_negatives":True,"unauthorized_business_and_success_audits":0,"site_navigation_parent_context":"Existing legitimate navigation A context remains; all four protected selectors blank for site-only actor"})
 print("Live HTTP security observations PASS:",len(records))

def positive():
 guard();request=login(ALIASES[0]);src=sources();org=Organization.objects.get(slug="demo-construction-01");results=[]
 for kind in ("transfer","receipt"):
  _,body,_=request(PATH);data=payload(kind);data["csrfmiddlewaretoken"]=Parsed(body).token
  before=snapshot();status,body,url=request(PATH,data)
  assert status==200 and url==BASE+"/inventory/transactions/",(status,url)
  record=StockTransaction.objects.get(organization=org,transaction_number=data["transaction_number"])
  assert record.status=="draft" and record.project_id==src["B"]["project"].pk
  assert AuditEvent.objects.filter(entity_id=record.pk,action=AuditAction.STOCK_TRANSACTION_CREATED).count()==1
  results.append({"kind":kind,"id":record.pk,"status":record.status,"project":record.project_id,"real_authenticated_csrf":True,"posted":False})
 save("RUNTIME_POSITIVE.json",results);print("Authorized live transfer and receipt drafts PASS; stock not posted")

def direct():
 guard();src=sources();org=Organization.objects.get(slug="demo-construction-01");results=[]
 for alias,keys in ((ALIASES[0],"CDX"),(ALIASES[2],"ABCDX")):
  for key in keys:
   actor=User.objects.get(username=alias);r=src[key];before=snapshot();denied=False
   try:create_stock_transaction(organization=org,actor=actor,transaction_number="B05-DIRECT-NEGATIVE",transaction_type="issue",source_warehouse=r["warehouse"],project=r["project"],material=src["B"]["item"].material,unit_of_measure=src["B"]["item"].unit_of_measure,quantity=Decimal(1),occurred_at=timezone.now())
   except PermissionDenied:denied=True
   assert denied and snapshot()==before
   results.append({"actor":alias,"source":key,"denied":denied,"mutations":0})
 save("DIRECT_SERVICE.json",results);print("Existing direct-service denials PASS:",len(results))

def src_item_id():
 return sources()["B"]["item"].pk

def after():
 guard();initial=json.loads((OUT/"RUNTIME_BEFORE.json").read_text());prep=json.loads((OUT/"PREPARATION_BEFORE.json").read_text());current=snapshot();rows=row_hashes()
 changed=[(m,pk) for m,rs in prep["rows"].items() if m!="sessions.Session" for pk,h in rs.items() if rows[m].get(pk)!=h]
 assert not changed,changed
 assert digest(authority())==digest(initial["authority"])
 deltas=[m for m,v in current.items() if v!=initial["models"][m]]
 assert set(deltas)<={"sessions.Session","inventory.StockTransaction","audit.AuditEvent"},deltas
 positives=json.loads((OUT/"RUNTIME_POSITIVE.json").read_text());ids={p["id"] for p in positives}
 added=set(rows["inventory.StockTransaction"])-set(initial["rows"]["inventory.StockTransaction"])
 assert added==ids and all(p["status"]=="draft" for p in positives)
 audit_added=set(rows["audit.AuditEvent"])-set(initial["rows"]["audit.AuditEvent"])
 assert AuditEvent.objects.filter(pk__in=audit_added,action=AuditAction.STOCK_TRANSACTION_CREATED).count()==2
 assert set(AuditEvent.objects.filter(pk__in=audit_added).values_list("action",flat=True))<={AuditAction.STOCK_TRANSACTION_CREATED,AuditAction.STOCK_RECEIPT_FAILED}
 assert not AuditEvent.objects.filter(pk__in=audit_added,action=AuditAction.STOCK_RECEIPT_FAILED).exclude(actor__username=ALIASES[0],entity_id=src_item_id()).exists()
 additions={m:len(set(rs)-set(prep["rows"][m])) for m,rs in rows.items() if set(rs)-set(prep["rows"][m])}
 assert set(additions)<={"sessions.Session","inventory.StockTransaction","inventory.Warehouse","procurement.PurchaseOrder","procurement.PurchaseOrderItem","procurement.PurchaseOrderVersion","procurement.PurchaseOrderVersionLine","procurement.GoodsReceipt","procurement.GoodsReceiptItem","audit.AuditEvent"},additions
 save("RUNTIME_AFTER.json",current)
 save("RUNTIME_INTEGRITY.json",{"tables":len(current),"preexisting_rows_changed":changed,"preparation_and_authorized_runtime_additions":additions,"runtime_deltas":deltas,"authorized_drafts":positives,"unauthorized_mutations":0,"retained_failure_audits":AuditEvent.objects.filter(pk__in=audit_added,action=AuditAction.STOCK_RECEIPT_FAILED).count(),"unauthorized_success_audits":0,"posted_stock_or_value_changes":0,"authority_unchanged":True,"authority_fingerprint_before":digest(initial["authority"]),"authority_fingerprint_after":digest(authority()),"temporary_authority":"NONE; cleanup not required","last_login_excluded":True})
 print("Runtime integrity PASS:",len(current),"tables; authority and all preexisting business rows preserved")

if __name__=="__main__":
 {"prepare":prepare,"http":http,"direct":direct,"positive":positive,"after":after}[sys.argv[1]]()
