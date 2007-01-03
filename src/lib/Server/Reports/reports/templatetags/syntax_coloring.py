from django import template

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    colorize = True
except:
    colorize = False
    
register = template.Library()

def syntaxhilight(value, arg="diff"):
    '''Returns a syntax-hilighted version of Code; requires code and language arguments'''
    lexer = get_lexer_by_name(arg)
    if colorize:
        try:
            return highlight(value, lexer, HtmlFormatter())
        except:
            return value
    else:
        return value


register.filter('syntaxhilight', syntaxhilight)
