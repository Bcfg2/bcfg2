from django import template
#from Bcfg2.Server.Reports.reports.models import Client, Interaction, Bad, Modified, Extra

register = template.Library()

def set_interaction(parser, token):
    try:
        # Splitting by None == splitting by spaces.
        tag_name, format_string = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires an argument" % token.contents[0]
    if not (format_string[0] == format_string[-1] and format_string[0] in ('"', "'")):
        raise template.TemplateSyntaxError, "%r tag's argument should be in quotes" % tag_name
    return SetInteraction(format_string[1:-1])

def sortwell(value):
    "sorts a list(or evaluates queryset to list) of bad, extra, or modified items in the best"
    "way for presentation"
    configItems = list(value)
    configItems.sort(lambda x,y: cmp(x.entry.name, y.entry.name))
    configItems.sort(lambda x,y: cmp(x.entry.kind, y.entry.kind))
    return configItems
def sortname(value):
    "sorts a list( or evaluates queryset) by name"
    configItems = list(value)
    configItems.sort(lambda x,y: cmp(x.name, y.name))
    return configItems
                                    
class SetInteraction(template.Node):
    def __init__(self, times):
        self.times = times#do soemthing to select different interaction with host?
    def render(self, context):
        try:
            context['interaction'] = context['client_interaction_dict'][context['client'].id]
        except:#I don't fully know what the implications of this are.
            pass
        return ''

register.tag('set_interaction', set_interaction)
register.filter('sortwell', sortwell)
register.filter('sortname', sortname)
