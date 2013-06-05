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
from django.db import connection, DatabaseError
from django.db.models import Q, Count

from Bcfg2.Reporting.models import *


__SORT_FIELDS__ = ( 'client', 'state', 'good', 'bad', 'modified', 'extra', \
            'timestamp', 'server' )

class PaginationError(Exception):
    """This error is raised when pagination cannot be completed."""
    pass


def _in_bulk(model, ids):
    """
    Short cut to fetch in bulk and trap database errors.  sqlite will raise
    a "too many SQL variables" exception if this list is too long.  Try using
    django and fetch manually if an error occurs

    returns a dict of this form { id: <model instance> }
    """

    try:
        return model.objects.in_bulk(ids)
    except DatabaseError:
        pass

    # if objects.in_bulk fails so will obejcts.filter(pk__in=ids)
    bulk_dict = {}
    [bulk_dict.__setitem__(i.id, i) \
        for i in model.objects.all() if i.id in ids]
    return bulk_dict


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
        if request.method == 'POST' and request.POST.get('op', '') == 'timeview':
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


def _handle_filters(query, **kwargs):
    """
    Applies standard filters to a query object

    Returns an updated query object

    query - query object to filter

    server -- Filter interactions by server
    state -- Filter interactions by state
    group -- Filter interactions by group

    """
    if 'state' in kwargs and kwargs['state']:
        query = query.filter(state__exact=kwargs['state'])
    if 'server' in kwargs and kwargs['server']:
        query = query.filter(server__exact=kwargs['server'])

    if 'group' in kwargs and kwargs['group']:
        group = get_object_or_404(Group, name=kwargs['group'])
        query = query.filter(groups__id=group.pk)
    return query


def config_item(request, pk, entry_type, interaction=None):
    """
    Display a single entry.

    Displays information about a single entry.

    """
    try:
        cls = BaseEntry.entry_from_name(entry_type)
    except ValueError:
        # TODO - handle this
        raise
    item = get_object_or_404(cls, pk=pk)

    # TODO - timestamp
    if interaction:
        try:
            inter = Interaction.objects.get(pk=interaction)
        except Interaction.DoesNotExist:
            raise Http404("Not a valid interaction")
        timestamp = inter.timestamp
    else:
        timestamp = datetime.now()

    ts_start = timestamp.replace(hour=1, minute=0, second=0, microsecond=0)
    ts_end = ts_start + timedelta(days=1)
    associated_list = item.interaction_set.select_related('client').filter(\
        timestamp__gte=ts_start, timestamp__lt=ts_end)

    if item.is_failure():
        template = 'config_items/item-failure.html'
    else:
        template = 'config_items/item.html'
    return render_to_response(template,
                              {'item': item,
                               'associated_list': associated_list,
                               'timestamp': timestamp},
                              context_instance=RequestContext(request))


@timeview
def config_item_list(request, item_state, timestamp=None, **kwargs):
    """Render a listing of affected elements"""
    state = convert_entry_type_to_id(item_state.lower())
    if state < 0:
        raise Http404

    current_clients = Interaction.objects.recent(timestamp)
    current_clients = [q['id'] for q in _handle_filters(current_clients, **kwargs).values('id')]

    lists = []
    for etype in ENTRY_TYPES:
        ldata = etype.objects.filter(state=state, interaction__in=current_clients)\
            .annotate(num_entries=Count('id')).select_related('linkentry', 'target_perms', 'current_perms')
        if len(ldata) > 0:
            # Property doesn't render properly..
            lists.append((etype.ENTRY_TYPE, ldata))

    return render_to_response('config_items/listing.html',
                              {'item_list': lists,
                               'item_state': item_state,
                               'timestamp': timestamp},
        context_instance=RequestContext(request))


@timeview
def entry_status(request, entry_type, pk, timestamp=None, **kwargs):
    """Render a listing of affected elements by type and name"""
    try:
        cls = BaseEntry.entry_from_name(entry_type)
    except ValueError:
        # TODO - handle this
        raise
    item = get_object_or_404(cls, pk=pk)

    current_clients = Interaction.objects.recent(timestamp)
    current_clients = [i['pk'] for i in _handle_filters(current_clients, **kwargs).values('pk')]

    # There is no good way to do this...
    items = []
    seen = []
    for it in cls.objects.filter(interaction__in=current_clients, name=item.name).select_related():
        if it.pk not in seen:
            items.append((it, it.interaction_set.filter(pk__in=current_clients).order_by('client__name').select_related('client')))
            seen.append(it.pk)

    return render_to_response('config_items/entry_status.html',
                              {'entry': item,
                               'items': items,
                               'timestamp': timestamp},
        context_instance=RequestContext(request))


@timeview
def common_problems(request, timestamp=None, threshold=None, group=None):
    """Mine config entries"""

    if request.method == 'POST':
        try:
            threshold = int(request.POST['threshold'])
            view, args, kw = resolve(request.META['PATH_INFO'])
            kw['threshold'] = threshold
            return HttpResponseRedirect(reverse(view,
                                                args=args,
                                                kwargs=kw))
        except:
            pass

    try:
        threshold = int(threshold)
    except:
        threshold = 10

    if group:
        group_obj = get_object_or_404(Group, name=group)
        current_clients = [inter[0] for inter in \
            Interaction.objects.recent(timestamp)\
                .filter(groups=group_obj).values_list('id')]
    else:
        current_clients = Interaction.objects.recent_ids(timestamp)
    lists = []
    for etype in ENTRY_TYPES:
        ldata = etype.objects.exclude(state=TYPE_GOOD).filter(
            interaction__in=current_clients).annotate(num_entries=Count('id')).filter(num_entries__gte=threshold)\
                .order_by('-num_entries', 'name')
        if len(ldata) > 0:
            # Property doesn't render properly..
            lists.append((etype.ENTRY_TYPE, ldata))

    return render_to_response('config_items/common.html',
                              {'lists': lists,
                               'timestamp': timestamp,
                               'threshold': threshold},
        context_instance=RequestContext(request))


@timeview
def client_index(request, timestamp=None, **kwargs):
    """
    Render a grid view of active clients.

    Keyword parameters:
      timestamp -- datetime object to render from

    """
    list = _handle_filters(Interaction.objects.recent(timestamp), **kwargs).\
           select_related('client').order_by("client__name").all()

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

    try:
        sort = request.GET['sort']
        if sort[0] == '-':
            sort_key = sort[1:]
        else:
            sort_key = sort
        if not sort_key in __SORT_FIELDS__:
            raise ValueError

        if sort_key == "client":
            kwargs['orderby'] = "%s__name" % sort
        elif sort_key in ["good", "bad", "modified", "extra"]:
            kwargs['orderby'] = "%s_count" % sort
        else:
            kwargs['orderby'] = sort
        kwargs['sort'] = sort
    except (ValueError, KeyError):
        kwargs['orderby'] = "client__name"
        kwargs['sort'] = "client"

    kwargs['interaction_base'] = \
        Interaction.objects.recent(timestamp).select_related()
    kwargs['page_limit'] = 0
    return render_history_view(request, 'clients/detailed-list.html', **kwargs)


def client_detail(request, hostname=None, pk=None):
    context = dict()
    client = get_object_or_404(Client, name=hostname)
    if(pk == None):
        inter = client.current_interaction
        maxdate = None
    else:
        inter = client.interactions.get(pk=pk)
        maxdate = inter.timestamp

    etypes = {TYPE_BAD: 'bad',
              TYPE_MODIFIED: 'modified',
              TYPE_EXTRA: 'extra'}
    edict = dict()
    for label in etypes.values():
        edict[label] = []
    for ekind in inter.entry_types:
        if ekind == 'failures':
            continue
        for ent in getattr(inter, ekind).all():
            edict[etypes[ent.state]].append(ent)
    context['entry_types'] = edict

    context['interaction'] = inter
    return render_history_view(request, 'clients/detail.html', page_limit=5,
        client=client, maxdate=maxdate, context=context)


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
                    (client_name,
                     client.expiration.strftime("%Y-%m-%d %H:%M:%S"))
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
    recent_data = Interaction.objects.recent(timestamp) \
        .select_related()
    node_count = len(recent_data)
    if not timestamp:
        timestamp = datetime.now()

    collected_data = dict(clean=[],
                          bad=[],
                          modified=[],
                          extra=[],
                          stale=[])
    for node in recent_data:
        if timestamp - node.timestamp > timedelta(hours=24):
            collected_data['stale'].append(node)
            # If stale check for uptime
        if node.bad_count > 0:
            collected_data['bad'].append(node)
        else:
            collected_data['clean'].append(node)
        if node.modified_count > 0:
            collected_data['modified'].append(node)
        if node.extra_count > 0:
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

    return render_to_response('displays/summary.html',
        {'summary_data': summary_data, 'node_count': node_count,
         'timestamp': timestamp},
        context_instance=RequestContext(request))


@timeview
def display_timing(request, timestamp=None):
    perfs = Performance.objects.filter(interaction__in=Interaction.objects.recent_ids(timestamp))\
        .select_related('interaction__client')

    mdict = dict()
    for perf in perfs:
        client = perf.interaction.client.name
        if client not in mdict:
            mdict[client] = { 'name': client }
        mdict[client][perf.metric] = perf.value

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
    group -- Filter interactions by group
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
        iquery = iquery.filter(client__exact=client)
    iquery = iquery.select_related('client')

    if 'orderby' in kwargs and kwargs['orderby']:
        iquery = iquery.order_by(kwargs['orderby'])
    if 'sort' in kwargs:
        context['sort'] = kwargs['sort']

    iquery = _handle_filters(iquery, **kwargs)

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
                                                               kwargs=kwargs)))
        except (Resolver404, NoReverseMatch, ValueError):
            raise "Accessing beyond last page.  Unable to resolve redirect."

    context['total_pages'] = total_pages
    context['records_per_page'] = max_results
    return (rec_start, rec_start + int(max_results))
