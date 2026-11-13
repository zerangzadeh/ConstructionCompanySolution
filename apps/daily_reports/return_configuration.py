"""Code-owned template for independent Return and legacy approval."""

from copy import deepcopy

RETURN_TEMPLATE_CODE = "daily_report_return_v1"
RETURN_COMMAND = "daily_reports.daily_report.return_for_correction"


def return_configuration(legacy):
    config = deepcopy(legacy)
    review = next(step for step in config["steps"] if step["key"] == "legacy_approval")
    legacy_review = deepcopy(review)
    legacy_review["key"] = "compatibility_approval"
    review["configuration"].update(exclude_creator=True, exclude_submitter=True)
    config["steps"].extend(
        [
            legacy_review,
            {
                "key": "returned",
                "name": "بازگشت برای اصلاح",
                "step_type": "end",
                "is_terminal": True,
            },
        ]
    )
    start = config["transitions"][0]
    start["outcome"] = "submitted_for_independent_review"
    start["is_default"] = False
    start["conditions"] = [
        {
            "condition_type": "subject_attribute_equals",
            "configuration": {"attribute": "return_enabled", "value": True},
        }
    ]
    config["transitions"].extend(
        [
            {
                "source": "start",
                "target": "compatibility_approval",
                "outcome": "submitted",
                "is_default": True,
            },
            {**config["transitions"][1], "source": "compatibility_approval"},
            {
                "source": "legacy_approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": RETURN_COMMAND,
                "required_permission": "daily_reports.approve",
            },
        ]
    )
    return config
