"""Explicit synthetic commercial choices for existing RFQ regression fixtures."""

from .commercial_scope_services import define_rfq_commercial_scope


def define_fixture_scopes(
    *, organization, actor, rfq, specifications=(("LINE-1", True),)
):
    rows = []
    for code, split in specifications:
        for index, line in enumerate(rfq.lines.all()):
            rows.append(
                {
                    "scope_type": "line",
                    "scope_code": code if index == 0 else f"{code}-{index}",
                    "required_quantity": line.quantity,
                    "lines": [
                        {
                            "purchase_request_item_id": str(
                                line.purchase_request_item_id
                            ),
                            "quantity": line.quantity,
                        }
                    ],
                    "independently_awardable": True,
                    "allows_split_award": split,
                    "allows_alternates": False,
                }
            )
    return define_rfq_commercial_scope(
        organization=organization,
        actor=actor,
        rfq=rfq,
        version_number=1,
        scopes=rows,
        expected_revision=0,
        idempotency_key="explicit-fixture-scope",
    )
