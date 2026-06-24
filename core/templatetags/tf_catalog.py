from django import template

from core.utils.category_display import category_display_name

register = template.Library()


@register.filter(name='category_label')
def category_label(value):
    return category_display_name(value)
