import json, os
from pathlib import Path
import psycopg

root = Path(os.environ["B06_TMP"])
settings = {"host":"127.0.0.1", "port":int((root/"db-port.txt").read_text().strip()), "user":"b06_local"}
queries = {
    "b06_validation": {
        "migration_count":"select count(*) from django_migrations",
        "b03_b04_related_migrations":"select app,name from django_migrations where (app='daily_reports' and (name like '0008%' or name like '0009%')) or (app='equipment' and name like '0006%') or (app='workflows' and name like '0028%') order by app,name",
        "base_tenants":"select count(*) from organizations_organization",
        "base_users":"select count(*) from accounts_user",
    },
    "test_b06_independent_count3": {
        "count":"select status, created_by_id <> approved_by_id from inventory_inventorycount where count_number='B06-COUNT'",
        "counted_lines":"select expected_quantity,counted_quantity,(adjustment_transaction_id is not null) from inventory_inventorycountline where inventory_count_id in (select id from inventory_inventorycount where count_number='B06-COUNT') order by expected_quantity",
        "audit_transitions":"select count(*) from audit_auditevent where entity_id in (select id::text from inventory_inventorycount where count_number='B06-COUNT')",
        "journal_entries":"select count(*) from accounting_journalentry",
    },
    "test_b06_independent_reservation3": {
        "reservations":"select status,quantity from inventory_inventoryreservation where reservation_number='B06-RES'",
        "reservation_audits":"select count(*) from audit_auditevent where entity_id in (select id::text from inventory_inventoryreservation where reservation_number='B06-RES')",
        "allocations":"select quantity,status from inventory_inventoryreservationallocation where reservation_id in (select id from inventory_inventoryreservation where reservation_number='B06-RES')",
        "movement_count":"select count(*) from inventory_stocktransaction",
        "journal_entries":"select count(*) from accounting_journalentry",
    },
    "test_b06_independent_transfer3": {
        "transfer":"select status, dispatched_by_id <> accepted_by_id from inventory_inventorytransfer where transfer_number='B06-TRANSFER'",
        "lineage":"select l.quantity,l.accepted_quantity, m1.quantity,m2.quantity, m1.id <> m2.id from inventory_inventorytransferline l join inventory_stocktransaction m1 on l.dispatch_transaction_id=m1.id join inventory_stocktransaction m2 on l.receipt_transaction_id=m2.id",
        "signed_movement_balance":"select w.code,sum(case when m.destination_warehouse_id=w.id then m.quantity else -m.quantity end) from inventory_warehouse w join inventory_stocktransaction m on w.id in (m.source_warehouse_id,m.destination_warehouse_id) where m.status in ('posted','reversed') group by w.code order by w.code",
        "audit_transitions":"select count(*) from audit_auditevent where entity_id in (select id::text from inventory_inventorytransfer where transfer_number='B06-TRANSFER')",
        "journal_entries":"select count(*) from accounting_journalentry",
    },
    "test_b06_independent_cancellation2": {
        "orders":"select status,count(*) from procurement_purchaseorder where order_number='B06-CANCEL' group by status",
        "rfqs":"select status,count(*) from procurement_requestforquotation group by status",
        "stock_movements":"select count(*) from inventory_stocktransaction",
    },
}
result={}
for db, statements in queries.items():
    with psycopg.connect(dbname=db, **settings) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        directory = Path(connection.execute("SHOW data_directory").fetchone()[0]).resolve()
        assert directory == (root/"pg").resolve()
        result[db]={"read_only": True, "postgresql_version": connection.execute("SHOW server_version").fetchone()[0]}
        for name, query in statements.items():
            result[db][name] = connection.execute(query).fetchall()
(root/"persisted-postgres.json").write_text(json.dumps(result,indent=2,default=str)+"\n",encoding="utf-8")
print(json.dumps(result,default=str))
