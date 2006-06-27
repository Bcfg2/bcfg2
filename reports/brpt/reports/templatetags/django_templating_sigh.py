from django import template
#from brpt.reports.models import Client, Interaction, Bad, Modified, Extra

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

                                    
class SetInteraction(template.Node):
    def __init__(self, times):
        self.times = times#do soemthing to select different interaction with host
    def render(self, context):
        #context['interaction'] = context['client'].interactions.latest('timestamp')
        context['interaction'] = context['client_interaction_dict'][context['client'].id]
        return ''

register.tag('set_interaction', set_interaction)
