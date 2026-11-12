from pathlib import Path

harness = Path(__file__).with_name('b04_browser_retest.py')
exec(harness.read_text(encoding='utf-8').split('\nwith sync_playwright()')[0], globals())

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    maker = login(browser, 'expense-control-maker')
    foreign = login(browser, 'b04-foreign')
    expense = get('expenses', 'Expense', source_reference='B04-INV1')
    detail = reverse('expenses:detail', args=[expense.pk])
    upload = reverse('documents:contextual-upload', args=['expense', expense.pk])
    link = reverse('documents:contextual-link', args=['expense', expense.pk])
    visit(maker, detail)
    main(maker).locator(f'a[href="{upload}"]').first.click()
    maker.wait_for_load_state('load')
    receipt = form(maker)
    fill(receipt, title='رسید آزمایشی B04', document_type='general')
    contents = b'%PDF-1.4\nB04 synthetic receipt only\n%%EOF'
    receipt.locator('[name=file]').set_input_files({'name': 'b04-receipt.pdf', 'mimeType': 'application/pdf', 'buffer': contents})
    capture(maker, 'expense-receipt-upload')
    click(receipt)
    doc = get('documents', 'Document', organization=expense.organization, title='رسید آزمایشی B04')
    links = model('expenses', 'ExpenseDocumentLink').objects.filter(expense=expense, document=doc)
    mark('expenses:receipt', links.count() == 1 and urlsplit(maker.url).path == detail, expense_id=expense.pk, document_id=doc.pk, version=doc.current_version_id, linked_rows=links.count())
    visit(maker, detail)
    capture(maker, 'expense-related-receipt')
    mark('expenses:receipt', doc.title in text(maker), visible_related_receipt=doc.title in text(maker))
    pending = reverse('documents:version-download', args=[doc.pk, doc.current_version_id])
    foreign_upload = foreign.request.get(base + upload).status
    foreign_download = foreign.request.get(base + pending).status
    pending_download = maker.request.get(base + pending).status
    mark('expenses:receipt', all(code in [403,404] for code in [foreign_upload, foreign_download, pending_download]), foreign_upload=foreign_upload, foreign_download=foreign_download, pending_download=pending_download)
    visit(maker, link)
    fields = form(maker).evaluate('(f) => Object.fromEntries(new FormData(f))')
    foreign_status = post(maker, link, {**fields, 'document': ids['doc']})
    mark('expenses:receipt', foreign_status in [400,403,404] and model('expenses', 'ExpenseDocumentLink').objects.filter(expense=expense).count() == 1, forged_foreign_document=foreign_status)
    browser.close()
save()
