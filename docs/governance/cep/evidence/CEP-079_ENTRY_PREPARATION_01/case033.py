"""New-target Inventory reversal/count/valuation evidence, no inferred GL policy."""
import json
from decimal import Decimal
import continue_uat as c
u=c.u
from apps.inventory.models import StockTransaction, Warehouse
from apps.inventory.services import reverse_stock_transaction, get_stock_balance
from apps.inventory.p8_services import (
    finalize_valuation, reverse_valuation, create_inventory_count,
    freeze_inventory_count, record_counted_quantity, submit_inventory_count,
    approve_inventory_count, post_inventory_count,
)

path=u.OUT/'UAT_CASE_033_RUNTIME.json'
data=json.loads(path.read_text(encoding='utf-8'))
def save():
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')

actor=u.actor('cep078.synthetic.operations')
stock=StockTransaction.objects.select_related('goods_receipt_item__purchase_order_item__purchase_order__current_version','material','destination_warehouse').get(organization=u.ORG,transaction_number='CEP079-UAT031-STOCK')
po_line=stock.goods_receipt_item.purchase_order_item.purchase_order.current_version.lines.get(source_item=stock.goods_receipt_item.purchase_order_item)
if 'valuation' not in data:
    event=finalize_valuation(organization=u.ORG,actor=actor,stock_transaction=stock,
        source_reference='procurement.PurchaseOrderVersionLine:'+str(po_line.pk),source_version=str(po_line.version.version_number),
        unit_cost=po_line.unit_price,idempotency_key='CEP079-033-value')
    data['valuation']={'event':str(event.pk),'source_version_line':str(po_line.pk),'unit_cost':str(po_line.unit_price),'value':str(event.value_amount),'at':u.timezone.now().isoformat()};save()
if 'stock_reversal' not in data:
    reversal=reverse_stock_transaction(organization=u.ORG,actor=actor,stock_transaction=stock,reversal_number='CEP079-UAT033-REVERSE',reason='CEP079 new receipt reversal preserves original and pinned value history')
    data['stock_reversal']=str(reversal.pk);save()
else:reversal=StockTransaction.objects.get(pk=data['stock_reversal'])
if 'value_reversal' not in data:
    reverse=reverse_valuation(organization=u.ORG,actor=actor,stock_transaction=reversal,idempotency_key='CEP079-033-value-reverse')
    data['value_reversal']={'event':str(reverse.pk),'reversal_of':str(reverse.reversal_of_id),'value':str(reverse.value_amount)};save()
if 'count' not in data:
    count=create_inventory_count(organization=u.ORG,actor=actor,count_number='CEP079-UAT033-COUNT',warehouse=stock.destination_warehouse)
    count=freeze_inventory_count(organization=u.ORG,actor=actor,inventory_count=count)
    data['count']=str(count.pk);data['frozen_lines']=list(count.lines.values('id','material_id','expected_quantity'));save()
    for line in count.lines.all():
        record_counted_quantity(organization=u.ORG,actor=actor,line=line,counted_quantity=Decimal('0.25'),variance_reason='Explicit synthetic UAT count assertion; disposable warehouse only')
    submit_inventory_count(organization=u.ORG,actor=actor,inventory_count=count)
    owner=u.actor('account.demo-construction-01.owner')
    approve_inventory_count(organization=u.ORG,actor=owner,inventory_count=count)
    count=post_inventory_count(organization=u.ORG,actor=owner,inventory_count=count)
    data['count_status']=count.status;data['independent_approver_and_poster']=owner.username;save()
balance=get_stock_balance(user=actor,organization=u.ORG,warehouse=stock.destination_warehouse,material=stock.material)
assert balance==Decimal('0.25')
data['final_source_balance']=str(balance);save()
print('Inventory native valuation/reversal/count complete; browser review pending')
