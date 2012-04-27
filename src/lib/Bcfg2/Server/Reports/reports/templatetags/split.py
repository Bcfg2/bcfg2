from django import template
register = template.Library()


@register.filter
def split(s):
    """split by newlines"""
    return s.split('\n')
