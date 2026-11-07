from django import template

from apps.accounts.templatetags.erp_format import erp_quantity_fa

register = template.Library()


@register.filter
def work_duration(minutes):
    hours, remainder = divmod(minutes, 60)
    if not hours:
        return f"{erp_quantity_fa(remainder)} دقیقه"
    if not remainder:
        return f"{erp_quantity_fa(hours)} ساعت"
    return f"{erp_quantity_fa(hours)} ساعت و {erp_quantity_fa(remainder)} دقیقه"
