"""Final real-HTTP Tender transitions; browser confirmation remains separate."""
from http_validation import request
from configure import *  # noqa: F403
from collections import Counter
from html.parser import HTMLParser
import hashlib

from apps.commercial.models import TenderBid


class IDs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for key, value in attrs if key == "id" and value)


def main():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    org = Organization.objects.get(slug="demo-construction-01")
    tender = TenderBid.objects.get(organization=org, opportunity_code="WCD-BROWSER")
    alias = "uiux.wavec.commercial"
    path = f"/commercial/{tender.pk}/"
    observations = []

    def observe(case, expected, data=None):
        status, body, _ = request(alias, path if data is None else path + "transition/", data)
        assert status == expected, (case, status)
        observations.append({"case": case, "status": status, "response_sha256": hashlib.sha256(body).hexdigest()})
        return body

    body = observe("Corrected detail forms", 200)
    parser = IDs()
    parser.feed(body.decode())
    assert not [name for name, count in Counter(parser.ids).items() if count > 1]
    assert b'transition_reason' in body and b'revision_reason' in body
    count = tender.revisions.count()
    observe("Submission without reference fails closed", 400, {"target": "submitted", "reason": LABEL})
    assert tender.revisions.count() == count
    for target, extra in [
        ("submitted", {"submission_reference": "WCD-SYNTHETIC-SUBMISSION"}),
        ("under_review", {}),
        ("lost", {"result_reference": "WCD-SYNTHETIC-RESULT"}),
    ]:
        observe("Canonical transition: " + target, 200, {"target": target, "reason": LABEL, **extra})
        assert tender.revisions.latest("version").status == target
    count = tender.revisions.count()
    observe("Terminal transition is rejected", 400, {"target": "won", "reason": LABEL, "result_reference": "forged"})
    assert tender.revisions.count() == count
    save("TENDER_HTTP_FINAL.json", {"tender": str(tender.pk), "observations": observations, "duplicate_dom_ids": [], "final_status": "lost", "browser_confirmation": "PENDING_WORK_SETTINGS_DISABLED"})
    print(f"Final Tender HTTP: {len(observations)}/{len(observations)} PASS; browser confirmation pending")


if __name__ == "__main__":
    main()
