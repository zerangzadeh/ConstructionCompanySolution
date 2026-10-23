"""Presentation labels from the registered Knowledge/source contracts."""

from django import template

from apps.knowledge.forms import ReviewForm, SourceForm
from apps.knowledge.models import KnowledgeAuthority

register = template.Library()


@register.filter
def knowledge_authority_label(value):
    return dict(KnowledgeAuthority.choices).get(value, "طبقه‌بندی ثبت‌شده")


@register.filter
def knowledge_review_label(value):
    return dict(ReviewForm.base_fields["outcome"].choices).get(value, "نتیجه ثبت‌شده")


@register.filter
def knowledge_source_label(value):
    return dict(SourceForm.base_fields["source_type"].choices).get(value, "منبع ثبت‌شده")


@register.filter
def knowledge_source_status_label(pin):
    # Status vocabulary belongs to each registered producer, never to Knowledge.
    from apps.knowledge.services import _source_registry

    contract = _source_registry().get(pin.source_type)
    if contract is None:
        return "وضعیت ثبت‌شده"
    field = contract[0]._meta.get_field("status")
    return dict(field.flatchoices).get(pin.source_status, "وضعیت ثبت‌شده")
