"""One external Development identity and canonical invite acceptance; no membership."""
from configure import *  # noqa: F403
import secrets
import subprocess
from datetime import timedelta

from apps.procurement.models import RequestForQuotationInvitation, SupplierPortalGrant, RequestForQuotation
from apps.procurement.rfq_services import create_rfq, add_rfq_line, submit_rfq_for_issue, issue_rfq
from apps.procurement.portal_services import create_supplier_portal_invitation, accept_supplier_portal_invitation


def fixture():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    org = Organization.objects.get(slug="demo-construction-01")
    alias = "uiux.wcd.external"
    external = User.objects.filter(username=alias).first()
    if external is None:
        password = secrets.token_urlsafe(32)
        external = User.objects.create_user(username=alias, email="wcd-external@example.test", password=password)
        # Same current-user DPAPI custody used by existing Wave C browser fixtures.
        command = "$d=[Console]::In.ReadToEnd()|ConvertFrom-Json; $p=Join-Path $env:LOCALAPPDATA 'BONIRA/UIUXRuntimeAudit/credentials'; [System.IO.Directory]::CreateDirectory($p)|Out-Null; $s=ConvertTo-SecureString $d.password -AsPlainText -Force; [pscredential]::new($d.alias,$s)|Export-Clixml -LiteralPath (Join-Path $p ($d.alias+'.clixml'))"
        subprocess.run(["pwsh", "-NoProfile", "-Command", command], input=json.dumps({"alias": alias, "password": password}), capture_output=True, text=True, check=True)
    assert not external.organization_memberships.exists() if hasattr(external, "organization_memberships") else not org.memberships.filter(user=external).exists()
    grant = SupplierPortalGrant.objects.filter(organization=org, principal__user=external).first()
    if grant is None:
        with transaction.atomic():
            source = RequestForQuotationInvitation.objects.get(organization=org, rfq_version__rfq__rfq_number="WAVE-C-RFQ-A")
            buyer = User.objects.get(username="uiux.persona.project-manager")
            issuer = User.objects.get(username="account.demo-construction-01.owner")
            closing = timezone.now() + timedelta(days=1)
            rfq = create_rfq(organization=org, actor=buyer, project=source.rfq_version.rfq.project, purchase_request=source.rfq_version.rfq.purchase_request, rfq_number="WCD-PORTAL-RFQ", title="نمونه توسعه — دریافت اصل پیشنهاد", closing_at=closing, earliest_opening_at=closing, terms=LABEL)
            for line in source.rfq_version.lines.all():
                add_rfq_line(organization=org, actor=buyer, rfq=rfq, purchase_request_item=line.purchase_request_item, quantity=line.quantity, description=LABEL)
            submit_rfq_for_issue(organization=org, actor=buyer, rfq=rfq)
            version = issue_rfq(organization=org, actor=issuer, rfq=rfq, suppliers=[source.supplier], idempotency_key="wcd-portal-issue")
            invitation = version.invitations.get()
            manager = User.objects.get(username="uiux.wavec.portal")
            _, token = create_supplier_portal_invitation(organization=org, actor=manager, rfq_invitation=invitation, invited_email=external.email, expires_at=timezone.now() + timedelta(hours=6))
            grant = accept_supplier_portal_invitation(actor=external, token=token)
    # A complete benign single-page PDF, with byte-accurate xref offsets.
    stream = b"BT /F1 12 Tf 36 140 Td (Wave C synthetic bid - UIUX TEST ONLY) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    payload, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(payload)); payload += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(payload)
    payload += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets)
    payload += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    (OUT / "synthetic_primary_bid.pdf").write_bytes(payload)
    save("PORTAL_FIXTURE.json", {"label": LABEL, "external_user": alias, "grant": str(grant.pk), "no_tenant_membership": not org.memberships.filter(user=external).exists()})
    print("Canonical external fixture ready; no Tenant membership or role changes")


if __name__ == "__main__":
    fixture()
