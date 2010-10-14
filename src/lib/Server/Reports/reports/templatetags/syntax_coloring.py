from django import template
from django.utils.encoding import smart_unicode, smart_str
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    colorize = True

except:
    colorize = False

@register.filter
def syntaxhilight(value, arg="diff", autoescape=None):
    """
    Returns a syntax-hilighted version of Code; requires code/language arguments
    """

    if autoescape:
        value = conditional_escape(value)
        arg = conditional_escape(arg)

    if colorize:
        try:
            output = u'<style  type="text/css">' \
                + smart_unicode(HtmlFormatter().get_style_defs('.highlight')) \
                + u'</style>'

            lexer = get_lexer_by_name(arg)
            output += highlight(value, lexer, HtmlFormatter())
            return mark_safe(output)
        except:
            return value
    else:
        return mark_safe(u'<div class="note-box">Tip: Install pygments for highlighting</div><pre>%s</pre>' % value)
syntaxhilight.needs_autoescape = True

