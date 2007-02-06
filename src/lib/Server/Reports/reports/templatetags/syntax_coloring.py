from django import template

register = template.Library()

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    colorize = True

except:
    colorize = False

def syntaxhilight(value, arg="diff"):
    '''Returns a syntax-hilighted version of Code; requires code/language arguments'''
    if colorize:
        try:
            lexer = get_lexer_by_name(arg)
            return highlight(value, lexer, HtmlFormatter())
        except:
            return value
    else:
        return value

register.filter('syntaxhilight', syntaxhilight)
