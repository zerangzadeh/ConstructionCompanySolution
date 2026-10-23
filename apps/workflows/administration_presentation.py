"""Read-only business labels for workflow administration review."""

from typing import Any

from apps.accounts.templatetags.erp_format import STATUS_LABELS

from .workbench import OUTCOME_LABELS


def business_review(configuration: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Project labels without changing the authoritative configuration or order."""
    labels = {}
    steps = []
    for index, step in enumerate(configuration["steps"], start=1):
        name = step["name"]
        if not name or name == step["key"]:
            number = str(index).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
            name = f"گام بدون عنوان کسب‌وکار ({number})"
        labels[step["key"]] = name
        steps.append({"name": name})
    transitions = [
        {
            "source": labels[item["source"]],
            "target": labels[item["target"]],
            "outcome": OUTCOME_LABELS.get(
                item["outcome"],
                STATUS_LABELS.get(
                    item["outcome"], "نتیجهٔ تعریف‌شده در پیکربندی پیشرفته"
                ),
            ),
        }
        for item in configuration["transitions"]
    ]
    return {"steps": steps, "transitions": transitions}
