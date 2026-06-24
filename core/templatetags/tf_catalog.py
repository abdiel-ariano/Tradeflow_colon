from django import template

from core.utils.category_display import category_display_name, category_icon_name

register = template.Library()


@register.filter(name='category_label')
def category_label(value):
    return category_display_name(value)


@register.filter(name='category_icon')
def category_icon(value):
    return category_icon_name(value)
