from django.template import Library

try:
    from django.templatetags.future import url as django_url
except ImportError:
    # future is removed in django 1.9
    from django.template.defaulttags import url as django_url

register = Library()


@register.tag
def url(parser, token):
    return django_url(parser, token)
