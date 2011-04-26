"""
Report views

Functions to handle all of the reporting views.
"""
from datetime import datetime, timedelta
import sys
from time import strptime

from django.template import Context, RequestContext
from django.http import \
        HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import \
        resolve, reverse, Resolver404, NoReverseMatch
from django.db import connection

from Bcfg2.Server.Reports.reports.models import *


class PaginationError(Exception):
    """This error is raised when pagination cannot be completed."""
    pass


def server_error(request):
    """
    500 error handler.

    For now always return the debug response.  Mailing isn't appropriate here.

    """
    from django.views import debug
    return debug.technical_500_response(request, *sys.exc_info())


def timeview(fn):
    """
    Setup a timeview view

    Handles backend posts from the calendar and converts date pieces
    into a 'timestamp' parameter

    """
    def _handle_timeview(request, **kwargs):
        """Send any posts back."""
        if request.method == 'POST':
            cal_date = request.POST['cal_date']
            try:
                fmt = "%Y/%m/%d"
                if cal_date.find(' ') > -1:
                    fmt += " %H:%M"
                timestamp = datetime(*strptime(cal_date, fmt)[0:6])
                view, args, kw = resolve(request.META['PATH_INFO'])
                kw['year'] = "%0.4d" % timestamp.year
                kw['month'] = "%02.d" % timestamp.month
                kw['day'] = "%02.d" % timestamp.day
                if cal_date.find(' ') > -1:
                    kw['hour'] = timestamp.hour
                    kw['minute'] = timestamp.minute
                return HttpResponseRedirect(reverse(view,
                                                    args=args,
                                                    kwargs=kw))
            except KeyError:
                pass
            except:
                pass
                # FIXME - Handle this

        """Extract timestamp from args."""
        timestamp = None
        try:
            timestamp = datetime(int(kwargs.pop('year')),
                                 int(kwargs.pop('month')),
                int(kwargs.pop('day')), int(kwargs.pop('hour', 0)),
                int(kwargs.pop('minute', 0)), 0)
            kwargs['timestamp'] = timestamp
        except KeyError:
            pass
        except:
            raise
        return fn(request, **kwargs)

    return _handle_timeview


def config_item(request, pk, type="bad"):
    """
    Display a single entry.

    Dispalys information about a single entry.

    """
    item = get_object_or_404(Entries_interactions, id=pk)
    timestamp = item.interaction.timestamp
    time_start = item.interaction.timestamp.replace(hour=0,
                                                    minute=0,
                                                    second=0,
                                                    microsecond=0)
    time_end = time_start + timedelta(days=1)

    todays_data = Interaction.objects.filter(timestamp__gte=time_start,
                                             timestamp__lt=time_end)
    shared_entries = Entries_interactions.objects.filter(entry=item.entry,
                                                         reason=item.reason,
                                                         type=item.type,
                                                         interaction__in=[x['id']\
                                                                          for x in todays_data.values('id')])

    associated_list = Interaction.objects.filter(id__in=[x['interaction']\
        for x in shared_entries.values('interaction')])\
        .order_by('client__name', 'timestamp').select_related().all()

    return render_to_response('config_items/item.html',
                              {'item': item,
                               'isextra': item.type == TYPE_EXTRA,
                               'mod_or_bad': type,
                               'associated_list': associated_list,
                               'timestamp': timestamp},
                              context_instance=RequestContext(request))


@timeview
def config_item_list(request, type, timestamp=None):
    """Render a listing of affected elements"""
    mod_or_bad = type.lower()
    type = convert_entry_type_to_id(type)
    if type < 0:
        raise Http404

    current_clients = Interaction.objects.get_interaction_per_client_ids(timestamp)
    item_list_dict = {}
    seen = dict()
    for x in Entries_interactions.objects.filter(interaction__in=current_clients,
                                                 type=type).select_related():
        if (x.entry, x.reason) in seen:
            continue
        seen[(x.entry, x.reason)] = 1
        if item_list_dict.get(x.entry.kind, None):
            item_list_dict[x.entry.kind].append(x)
        else:
            item_list_dict[x.entry.kind] = [x]

    for kind in item_list_dict:
        item_list_dict[kind].sort(lambda a, b: cmp(a.entry.name, b.entry.name))

    return render_to_response('config_items/listing.html',
                              {'item_list_dict': item_list_dict,
                               'mod_or_bad': mod_or_bad,
                               'timestamp': timestamp},
        context_instance=RequestContext(request))


@timeview
def client_index(request, timestamp=None):
    """
    Render a grid view of active clients.

    Keyword parameters:
      timestamp -- datetime objectto render from

    """
    list = Interaction.objects.interaction_per_client(timestamp).select_related()\
           .order_by("client__name").all()

    return render_to_response('clients/index.html',
                              {'inter_list': list,
                               'timestamp': timestamp},
                              context_instance=RequestContext(request))


@timeview
def client_detailed_list(request, timestamp=None, **kwargs):
    """
    Provides a more detailed list view of the clients.  Allows for extra
    filters to be passed in.

    """

    kwargs['interaction_base'] = Interaction.objects.interaction_per_client(timestamp).select_related()
    kwargs['orderby'] = "client__name"
    kwargs['page_limit'] = 0
    return render_history_view(request, 'clients/detailed-list.html', **kwargs)


def client_detail(request, hostname=None, pk=None):
    context = dict()
    client = get_object_or_404(Client, name=hostname)
    if(pk == None):
        context['interaction'] = client.current_interaction
        return render_history_view(request, 'clients/detail.html', page_limit=5,
            client=client, context=context)
    else:
        context['interaction'] = client.interactions.get(pk=pk)
        return render_history_view(request, 'clients/detail.html', page_limit=5,
            client=client, maxdate=context['interaction'].timestamp, context=context)


def client_manage(request):
    """Manage client expiration"""
    message = ''
    if request.method == 'POST':
        try:
            client_name = request.POST.get('client_name', None)
            client_action = request.POST.get('client_action', None)
            client = Client.objects.get(name=client_name)
            if client_action == 'expire':
                client.expiration = datetime.now()
                client.save()
                message = "Expiration for %s set to %s." % \
                    (client_name, client.expiration.strftime("%Y-%m-%d %H:%M:%S"))
            elif client_action == 'unexpire':
                client.expiration = None
                client.save()
                message = "%s is now active." % client_name
            else:
                message = "Missing action"
        except Client.DoesNotExist:
            if not client_name:
                client_name = "<none>"
            message = "Couldn't find client \"%s\"" % client_name

    return render_to_response('clients/manage.html',
        {'clients': Client.objects.order_by('name').all(), 'message': message},
        context_instance=RequestContext(request))


@timeview
def display_summary(request, timestamp=None):
    """
    Display a summary of the bcfg2 world
    """
    query = Interaction.objects.interaction_per_client(timestamp).select_related()
    node_count = query.count()
    recent_data = query.all()
    if not timestamp:
        timestamp = datetime.now()

    collected_data = dict(clean=[],
                          bad=[],
                          modified=[],
                          extra=[],
                          stale=[],
                          pings=[])
    for node in recent_data:
        if timestamp - node.timestamp > timedelta(hours=24):
            collected_data['stale'].append(node)
            # If stale check for uptime
        try:
            if node.client.pings.latest().status == 'N':
                collected_data['pings'].append(node)
        except Ping.DoesNotExist:
            collected_data['pings'].append(node)
            continue
        if node.bad_entry_count() > 0:
            collected_data['bad'].append(node)
        else:
            collected_data['clean'].append(node)
        if node.modified_entry_count() > 0:
            collected_data['modified'].append(node)
        if node.extra_entry_count() > 0:
            collected_data['extra'].append(node)

    # label, header_text, node_list
    summary_data = []
    get_dict = lambda name, label: {'name': name,
                                    'nodes': collected_data[name],
                                    'label': label}
    if len(collected_data['clean']) > 0:
        summary_data.append(get_dict('clean',
                                     'nodes are clean.'))
    if len(collected_data['bad']) > 0:
        summary_data.append(get_dict('bad',
                                     'nodes are bad.'))
    if len(collected_data['modified']) > 0:
        summary_data.append(get_dict('modified',
                                     'nodes were modified.'))
    if len(collected_data['extra']) > 0:
        summary_data.append(get_dict('extra',
                                     'nodes have extra configurations.'))
    if len(collected_data['stale']) > 0:
        summary_data.append(get_dict('stale',
                                     'nodes did not run within the last 24 hours.'))
    if len(collected_data['pings']) > 0:
        summary_data.append(get_dict('pings',
                                     'are down.'))

    return render_to_response('displays/summary.html',
        {'summary_data': summary_data, 'node_count': node_count,
         'timestamp': timestamp},
        context_instance=RequestContext(request))


@timeview
def display_timing(request, timestamp=None):
    mdict = dict()
    inters = Interaction.objects.interaction_per_client(timestamp).select_related().all()
    [mdict.__setitem__(inter, {'name': inter.client.name}) \
        for inter in inters]
    for metric in Performance.objects.filter(interaction__in=list(mdict.keys())).all():
        for i in metric.interaction.all():
            mdict[i][metric.metric] = metric.value
    return render_to_response('displays/timing.html',
                              {'metrics': list(mdict.values()),
                               'timestamp': timestamp},
                              context_instance=RequestContext(request))


def render_history_view(request, template='clients/history.html', **kwargs):
    """
    Provides a detailed history of a clients interactions.

    Renders a detailed history of a clients interactions. Allows for various
    filters and settings.  Automatically sets pagination data into the context.

    Keyword arguments:
    interaction_base -- Interaction QuerySet to build on
                        (default Interaction.objects)
    context -- Additional context data to render with
    page_number -- Page to display (default 1)
    page_limit -- Number of results per page, if 0 show all (default 25)
    client -- Client object to render
    hostname -- Client hostname to lookup and render.  Returns a 404 if
                not found
    server -- Filter interactions by server
    state -- Filter interactions by state
    entry_max -- Most recent interaction to display
    orderby -- Sort results using this field

    """

    context = kwargs.get('context', dict())
    max_results = int(kwargs.get('page_limit', 25))
    page = int(kwargs.get('page_number', 1))

    client = kwargs.get('client', None)
    if not client and 'hostname' in kwargs:
        client = get_object_or_404(Client, name=kwargs['hostname'])
    if client:
        context['client'] = client

    entry_max = kwargs.get('maxdate', None)
    context['entry_max'] = entry_max

    # Either filter by client or limit by clients
    iquery = kwargs.get('interaction_base', Interaction.objects)
    if client:
        iquery = iquery.filter(client__exact=client).select_related()

    if 'orderby' in kwargs and kwargs['orderby']:
        iquery = iquery.order_by(kwargs['orderby'])

    if 'state' in kwargs and kwargs['state']:
        iquery = iquery.filter(state__exact=kwargs['state'])
    if 'server' in kwargs and kwargs['server']:
        iquery = iquery.filter(server__exact=kwargs['server'])

    if entry_max:
        iquery = iquery.filter(timestamp__lte=entry_max)

    if max_results < 0:
        max_results = 1
    entry_list = []
    if max_results > 0:
        try:
            rec_start, rec_end = prepare_paginated_list(request,
                                                        context,
                                                        iquery,
                                                        page,
                                                        max_results)
        except PaginationError:
            page_error = sys.exc_info()[1]
            if isinstance(page_error[0], HttpResponse):
                return page_error[0]
            return HttpResponseServerError(page_error)
        context['entry_list'] = iquery.all()[rec_start:rec_end]
    else:
        context['entry_list'] = iquery.all()

    return render_to_response(template, context,
                context_instance=RequestContext(request))


def prepare_paginated_list(request, context, paged_list, page=1, max_results=25):
    """
    Prepare context and slice an object for pagination.
    """
    if max_results < 1:
        raise PaginationError("Max results less then 1")
    if paged_list == None:
        raise PaginationError("Invalid object")

    try:
        nitems = paged_list.count()
    except TypeError:
        nitems = len(paged_list)

    rec_start = (page - 1) * int(max_results)
    try:
        total_pages = (nitems / int(max_results)) + 1
    except:
        total_pages = 1
    if page > total_pages:
        # If we passed beyond the end send back
        try:
            view, args, kwargs = resolve(request.META['PATH_INFO'])
            kwargs['page_number'] = total_pages
            raise PaginationError(HttpResponseRedirect(reverse(view,
                                                               kwards=kwargs)))
        except (Resolver404, NoReverseMatch, ValueError):
            raise "Accessing beyond last page.  Unable to resolve redirect."

    context['total_pages'] = total_pages
    context['records_per_page'] = max_results
    return (rec_start, rec_start + int(max_results))
