from django import template
from django.core.urlresolvers import resolve, reverse, Resolver404, NoReverseMatch
from django.utils.encoding import smart_unicode, smart_str
from datetime import datetime, timedelta
from Bcfg2.Server.Reports.utils import filter_list

register = template.Library()

__PAGE_NAV_LIMITS__ = (10, 25, 50, 100)

@register.inclusion_tag('widgets/page_bar.html', takes_context=True)
def page_navigator(context):
    """
    Creates paginated links.

    Expects the context to be a RequestContext and views.prepare_paginated_list()
    to have populated page information.
    """
    fragment = dict()
    try:
        path = context['request'].META['PATH_INFO']
        total_pages = int(context['total_pages'])
        records_per_page = int(context['records_per_page'])
    except KeyError:
        return fragment
    except ValueError:
        return fragment

    if total_pages < 2:
        return {}

    try:
       view, args, kwargs = resolve(path)
       current_page = int(kwargs.get('page_number',1))
       fragment['current_page'] = current_page
       fragment['page_number'] = current_page
       fragment['total_pages'] = total_pages
       fragment['records_per_page'] = records_per_page
       if current_page > 1:
           kwargs['page_number'] = current_page - 1
           fragment['prev_page'] = reverse(view, args=args, kwargs=kwargs)
       if current_page < total_pages:
           kwargs['page_number'] = current_page + 1
           fragment['next_page'] = reverse(view, args=args, kwargs=kwargs)

       view_range = 5
       if total_pages > view_range:
           pager_start = current_page - 2
           pager_end = current_page + 2
           if pager_start < 1:
               pager_end += (1 - pager_start)
               pager_start = 1
           if pager_end > total_pages:
               pager_start -= (pager_end - total_pages)
               pager_end = total_pages
       else:
           pager_start = 1
           pager_end = total_pages

       if pager_start > 1:
           kwargs['page_number'] = 1
           fragment['first_page'] = reverse(view, args=args, kwargs=kwargs)
       if pager_end < total_pages:
           kwargs['page_number'] = total_pages
           fragment['last_page'] = reverse(view, args=args, kwargs=kwargs)

       pager = []
       for page in range(pager_start, int(pager_end) + 1):
           kwargs['page_number'] = page
           pager.append( (page, reverse(view, args=args, kwargs=kwargs)) )

       kwargs['page_number'] = 1
       page_limits = []
       for limit in __PAGE_NAV_LIMITS__:
           kwargs['page_limit'] = limit
           page_limits.append( (limit, reverse(view, args=args, kwargs=kwargs)) )
       # resolver doesn't like this
       del kwargs['page_number']
       del kwargs['page_limit']
       page_limits.append( ('all', reverse(view, args=args, kwargs=kwargs) + "|all") )

       fragment['pager'] = pager
       fragment['page_limits'] = page_limits
              
    except Resolver404:
       path = "404"
    except NoReverseMatch:
       nr = sys.exc_info()[1]
       path = "NoReverseMatch: %s" % nr
    except ValueError:
       path = "ValueError"
    #FIXME - Handle these

    fragment['path'] = path
    return fragment

@register.inclusion_tag('widgets/filter_bar.html', takes_context=True)
def filter_navigator(context):
    try:
        path = context['request'].META['PATH_INFO']
        view, args, kwargs = resolve(path)

        # Strip any page limits and numbers
        if 'page_number' in kwargs:
            del kwargs['page_number']
        if 'page_limit' in kwargs:
            del kwargs['page_limit']

        filters = []
        for filter in filter_list:
            if filter in kwargs:
                myargs = kwargs.copy()
                del myargs[filter]
                filters.append( (filter, reverse(view, args=args, kwargs=myargs) ) )
        filters.sort(lambda x,y: cmp(x[0], y[0]))
        return { 'filters': filters }
    except (Resolver404, NoReverseMatch, ValueError, KeyError):
        pass
    return dict()

def _subtract_or_na(mdict, x, y):
    """
    Shortcut for build_metric_list
    """
    try:
        return round(mdict[x] - mdict[y], 4)
    except:
        return "n/a"

@register.filter
def build_metric_list(mdict):
    """
    Create a list of metric table entries

    Moving this here it simplify the view.  Should really handle the case where these
    are missing...
    """
    td_list = []
    # parse
    td_list.append( _subtract_or_na(mdict, 'config_parse', 'config_download'))
    #probe
    td_list.append( _subtract_or_na(mdict, 'probe_upload', 'start'))
    #inventory
    td_list.append( _subtract_or_na(mdict, 'inventory', 'initialization'))
    #install
    td_list.append( _subtract_or_na(mdict, 'install', 'inventory'))
    #cfg download & parse
    td_list.append( _subtract_or_na(mdict, 'config_parse', 'probe_upload'))
    #total
    td_list.append( _subtract_or_na(mdict, 'finished', 'start'))
    return td_list

@register.filter
def isstale(timestamp, entry_max=None):
    """
    Check for a stale timestamp

    Compares two timestamps and returns True if the 
    difference is greater then 24 hours.
    """
    if not entry_max:
        entry_max = datetime.now()
    return entry_max - timestamp > timedelta(hours=24)

@register.filter
def sort_interactions_by_name(value):
    """
    Sort an interaction list by client name
    """
    inters = list(value)
    inters.sort(lambda a,b: cmp(a.client.name, b.client.name))
    return inters

class AddUrlFilter(template.Node):
    def __init__(self, filter_name, filter_value):
        self.filter_name = filter_name
        self.filter_value = filter_value
        self.fallback_view = 'Bcfg2.Server.Reports.reports.views.render_history_view'

    def render(self, context):
        link = '#'
        try:
            path = context['request'].META['PATH_INFO']
            view, args, kwargs = resolve(path)
            filter_value = self.filter_value.resolve(context, True)
            if filter_value:
                filter_name = smart_str(self.filter_name)
                filter_value = smart_unicode(filter_value)
                kwargs[filter_name] = filter_value
                # These two don't make sense
                if filter_name == 'server' and 'hostname' in kwargs:
                    del kwargs['hostname']
                elif filter_name == 'hostname' and 'server' in kwargs:
                    del kwargs['server']
                try:
                    link = reverse(view, args=args, kwargs=kwargs)
                except NoReverseMatch:
                    link = reverse(self.fallback_view, args=None,
                        kwargs={ filter_name: filter_value })
        except NoReverseMatch:
            rm = sys.exc_info()[1]
            raise rm
        except (Resolver404, ValueError):
            pass
        return link

@register.tag
def add_url_filter(parser, token):
    """
    Return a url with the filter added to the current view.

    Takes a new filter and resolves the current view with the new filter
    applied.  Resolves to Bcfg2.Server.Reports.reports.views.client_history
    by default.

    {% add_url_filter server=interaction.server %}
    """
    try:
        tag_name, filter_pair = token.split_contents()
        filter_name, filter_value = filter_pair.split('=', 1)
        filter_name = filter_name.strip()
        filter_value = parser.compile_filter(filter_value)
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires exactly one argument" % token.contents.split()[0])
    if not filter_name or not filter_value:
        raise template.TemplateSyntaxError("argument should be a filter=value pair")

    return AddUrlFilter(filter_name, filter_value)

@register.filter
def sortwell(value):
    """
    Sorts a list(or evaluates queryset to list) of bad, extra, or modified items in the best
    way for presentation
    """

    configItems = list(value)
    configItems.sort(lambda x,y: cmp(x.entry.name, y.entry.name))
    configItems.sort(lambda x,y: cmp(x.entry.kind, y.entry.kind))
    return configItems

class MediaTag(template.Node):
    def __init__(self, filter_value):
        self.filter_value = filter_value

    def render(self, context):
        base = context['MEDIA_URL']
        try:
           request = context['request']
           try:
               base = request.environ['bcfg2.media_url']
           except:
               if request.path != request.META['PATH_INFO']:
                   offset = request.path.find(request.META['PATH_INFO'])
                   if offset > 0:
                       base = "%s/%s" % (request.path[:offset], \
                               context['MEDIA_URL'].strip('/'))
        except:
            pass
        return "%s/%s" % (base, self.filter_value)

@register.tag
def to_media_url(parser, token):
    """
    Return a url relative to the media_url.

    {% to_media_url /bcfg2.css %}
    """
    try:
        tag_name, filter_value = token.split_contents()
        filter_value = parser.compile_filter(filter_value)
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires exactly one argument" % token.contents.split()[0])

    return MediaTag(filter_value)

