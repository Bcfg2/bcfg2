# Create your views here.
#from django.shortcuts import get_object_or_404, render_to_response
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from Bcfg2.Server.Reports.reports.models import Client, Interaction, Entries, Entries_interactions, Performance, Reason
from Bcfg2.Server.Reports.reports.models import TYPE_BAD, TYPE_MODIFIED, TYPE_EXTRA
from datetime import datetime, timedelta
from time import strptime
from django.db import connection
from django.db.backends import util
from django.contrib.auth.decorators import login_required

def index(request):
    return render_to_response('index.html')

def config_item_modified(request, eyedee =None, timestamp = 'now', type=TYPE_MODIFIED):
    #if eyedee = None, dump with a 404
    timestamp = timestamp.replace("@"," ")
    if type == TYPE_MODIFIED:
        mod_or_bad = "modified"
    else:
        mod_or_bad = "bad"
    
    item = Entries_interactions.objects.get(id=eyedee).entry
    #if everything is blank except current_exists, do something special
    cursor = connection.cursor()
    if timestamp == 'now':
        cursor.execute("select client_id from reports_interaction, reports_entries_interactions, reports_client "+
                   "WHERE reports_client.current_interaction_id = reports_entries_interactions.interaction_id "+
                   "AND reports_entries_interactions.interaction_id = reports_interaction.id "+
                   "AND reports_entries_interactions.entry_id = %s " +
                   "AND reports_entries_interactions.type = %s", [eyedee, type])
        associated_client_list = Client.objects.active(timestamp).filter(id__in=[x[0] for x in cursor.fetchall()])
    else:
        interact_queryset = Interaction.objects.interaction_per_client(timestamp)
        interactionlist = []
        [interactionlist.append(x.id) for x in interact_queryset]
        if not interactionlist == []:
            cursor.execute("select client_id from reports_interaction, reports_entries_interactions, reports_client "+
                   "WHERE reports_entries_interactions.interaction_id IN %s "+
                   "AND reports_entries_interactions.interaction_id = reports_interaction.id "+
                   "AND reports_entries_interactions.modified_id = %s " +
                   "AND reports_entries_interactions.type = %s ", [interactionlist, eyedee, type])
            associated_client_list = Client.objects.active(timestamp).filter(id__in=[x[0] for x in cursor.fetchall()])
        else:
            associated_client_list = []

    if timestamp == 'now':
        timestamp = datetime.now().isoformat('@')

    return render_to_response('config_items/index.html', {'item':item,
                                                         'mod_or_bad':mod_or_bad,
                                                         'associated_client_list':associated_client_list,
                                                         'timestamp' : timestamp,
                                                         'timestamp_date' : timestamp[:10],
                                                         'timestamp_time' : timestamp[11:19]})


def config_item_bad(request, eyedee = None, timestamp = 'now'):
    return config_item_modified(request, eyedee, timestamp, TYPE_BAD)

def bad_item_index(request, timestamp = 'now', type=TYPE_BAD):
    timestamp = timestamp.replace("@"," ")
    if type == TYPE_BAD:
        mod_or_bad = "bad"
    else:
        mod_or_bad = "modified"
    
    current_clients = [c.current_interaction
                       for c in Client.objects.active(timestamp)]
    item_list_dict = {}
    for x in Entries_interactions.objects.select_related().filter(interaction__in=current_clients, type=type).distinct():
        if item_list_dict.get(x.entry.kind, None):
            item_list_dict[x.entry.kind].append(x)
        else:
            item_list_dict[x.entry.kind] = [x]

    item_list_pseudodict = item_list_dict.items()
    if timestamp == 'now':
        timestamp = datetime.now().isoformat('@')

    return render_to_response('config_items/listing.html', {'item_list_pseudodict':item_list_pseudodict,
                                                            'mod_or_bad':mod_or_bad,
                                                            'timestamp' : timestamp,
                                                            'timestamp_date' : timestamp[:10],
                                                            'timestamp_time' : timestamp[11:19]})
def modified_item_index(request, timestamp = 'now'):
    return bad_item_index(request, timestamp, TYPE_MODIFIED)

def client_index(request, timestamp = 'now'):
    timestamp = timestamp.replace("@"," ")
    client_list = Client.objects.active(timestamp).order_by('name')
    client_list_b = client_list[:len(client_list)/2]
    client_list_a = client_list[len(client_list)/2:]
    if timestamp == 'now':
        timestamp = datetime.now().isoformat('@')
    return render_to_response('clients/index.html',
           {'client_list_a': client_list_a,
            'client_list_b': client_list_b,
            'timestamp' : timestamp,
            'timestamp_date' : timestamp[:10],
            'timestamp_time' : timestamp[11:19]})

def client_detail(request, hostname = None, pk = None):
    #SETUP error pages for when you specify a client or interaction that doesn't exist
    client = get_object_or_404(Client, name=hostname)
    if(pk == None):
        interaction = client.current_interaction
    else:
        interaction = client.interactions.get(pk=pk)#can this be a get object or 404?
    return render_to_response('clients/detail.html', {'client': client, 'interaction': interaction})

def client_manage(request, hostname = None):
    #SETUP error pages for when you specify a client or interaction that doesn't exist
    client = get_object_or_404(Client, name=hostname)
    currenttime = datetime.now().isoformat('@')
    if client.expiration != None:
        message = ("This client currently has an expiration date of %s. "
                   "Reports after %s will not include data for this host "
                   "You may change this if you wish by selecting a new "
                   "time, earlier or later."
                   % (client.expiration, client.expiration))
    else:
        message = ("This client is currently active and displayed. You "
                   "may choose a date after which this client will no "
                   "longer appear in reports.")
    if request.method == 'POST':
        date = request.POST['date1']
        time = request.POST['time']
        try:
            timestamp = datetime(*(strptime(date+"@"+time, "%Y-%m-%d@%H:%M:%S")[0:6]))
        except ValueError:
            timestamp = None
        if timestamp == None:
            message = "Invalid removal date, please try again using the format: yyyy-mm-dd hh:mm:ss."
        else:
            client.expiration = timestamp
            client.save()
            message = "Expiration for client set to %s." % client.expiration
    return render_to_response('clients/manage.html', {'client': client, 'message': message,
                                                      'timestamp_date' : currenttime[:10],
                                                      'timestamp_time' : currenttime[11:19]})

def display_sys_view(request, timestamp = 'now'):
    client_lists = prepare_client_lists(request, timestamp)
    return render_to_response('displays/sys_view.html', client_lists)

def display_summary(request, timestamp = 'now'):
    
    client_lists = prepare_client_lists(request, timestamp)
    #this returns timestamp and the timestamp parts too
    return render_to_response('displays/summary.html', client_lists)

def display_timing(request, timestamp = 'now'):
    #We're going to send a list of dictionaries. Each dictionary will be a row in the table
    #+------+-------+----------------+-----------+---------+----------------+-------+
    #| name | parse | probe download | inventory | install | cfg dl & parse | total |
    #+------+-------+----------------+-----------+---------+----------------+-------+
    client_list = Client.objects.active(timestamp.replace("@"," ")).order_by('name')
    stats_list = []

    if not timestamp == 'now':
        results = Performance.objects.performance_per_client(timestamp.replace("@"," "))
    else:
        results = Performance.objects.performance_per_client()
        timestamp = datetime.now().isoformat('@')
        
    for client in client_list:#Go explicitly to an interaction ID! (new item in dictionary)
        try:
            d = results[client.name]
        except KeyError:
            d = {}

        dict_unit = {}
        try:
            dict_unit["name"] = client.name #node name
        except:
            dict_unit["name"] = "n/a"
        try:
            dict_unit["parse"] = round(d["config_parse"] - d["config_download"], 4) #parse
        except:
            dict_unit["parse"] = "n/a"
        try:
            dict_unit["probe"] = round(d["probe_upload"] - d["start"], 4) #probe
        except:
            dict_unit["probe"] = "n/a"
        try:
            dict_unit["inventory"] = round(d["inventory"] - d["initialization"], 4) #inventory
        except:
            dict_unit["inventory"] = "n/a"
        try:
            dict_unit["install"] = round(d["install"] - d["inventory"], 4) #install
        except:
            dict_unit["install"] = "n/a"
        try:
            dict_unit["config"] = round(d["config_parse"] - d["probe_upload"], 4)#config download & parse
        except:
            dict_unit["config"] = "n/a"
        try:
            dict_unit["total"] = round(d["finished"] - d["start"], 4) #total
        except:
            dict_unit["total"] = "n/a"

        stats_list.append(dict_unit)

    return render_to_response('displays/timing.html', {'client_list': client_list,
                                                      'stats_list': stats_list,
                                                      'timestamp' : timestamp,
                                                      'timestamp_date' : timestamp[:10],
                                                      'timestamp_time' : timestamp[11:19]})

def display_index(request):
    return render_to_response('displays/index.html')

def prepare_client_lists(request, timestamp = 'now'):
    #I suggest we implement "expiration" here.

    timestamp = timestamp.replace("@"," ")
    #client_list = Client.objects.all().order_by('name')#change this to order by interaction's state
    client_interaction_dict = {}
    clean_client_list = []
    bad_client_list = []
    extra_client_list = []
    modified_client_list = []
    stale_up_client_list = []
    #stale_all_client_list = []
    down_client_list = []

    cursor = connection.cursor()

    interact_queryset = Interaction.objects.interaction_per_client(timestamp)
    # or you can specify a time like this: '2007-01-01 00:00:00'
    [client_interaction_dict.__setitem__(x.client_id, x) for x in interact_queryset]
    client_list = Client.objects.active(timestamp).filter(id__in=client_interaction_dict.keys()).order_by('name')

    [clean_client_list.append(x) for x in Client.objects.active(timestamp).filter(id__in=[y.client_id for y in interact_queryset.filter(state='clean')])]
    [bad_client_list.append(x) for x in Client.objects.active(timestamp).filter(id__in=[y.client_id for y in interact_queryset.filter(state='dirty')])]

    client_ping_dict = {}
    [client_ping_dict.__setitem__(x,'Y') for x in client_interaction_dict.keys()]#unless we know otherwise...
    
    try:
        cursor.execute("select reports_ping.status, x.client_id from (select client_id, MAX(endtime) "+
                       "as timer from reports_ping GROUP BY client_id) x, reports_ping where "+
                       "reports_ping.client_id = x.client_id AND reports_ping.endtime = x.timer")
        [client_ping_dict.__setitem__(x[1], x[0]) for x in cursor.fetchall()]
    except:
        pass #This is to fix problems when you have only zero records returned

    client_down_ids = [y for y in client_ping_dict.keys() if client_ping_dict[y]=='N']
    if not client_down_ids == []:
        [down_client_list.append(x) for x in Client.objects.active(timestamp).filter(id__in=client_down_ids)]

    if (timestamp == 'now' or timestamp == None): 
        cursor.execute("select client_id, MAX(timestamp) as timestamp from reports_interaction GROUP BY client_id")
        results = cursor.fetchall()
        for x in results:
            if type(x[1]) == type(""):
                x[1] = util.typecast_timestamp(x[1])
        stale_all_client_list = Client.objects.active(timestamp).filter(id__in=[x[0] for x in results if datetime.now() - x[1] > timedelta(days=1)])
    else:
        cursor.execute("select client_id, timestamp, MAX(timestamp) as timestamp from reports_interaction "+
                       "WHERE timestamp < %s GROUP BY client_id", [timestamp])
        t = strptime(timestamp,"%Y-%m-%d %H:%M:%S")
        datetimestamp = datetime(t[0], t[1], t[2], t[3], t[4], t[5])
        results = cursor.fetchall()
        for x in results:
            if type(x[1]) == type(""):
                x[1] = util.typecast_timestamp(x[1])
        stale_all_client_list = Client.objects.active(timestamp).filter(id__in=[x[0] for x in results if datetimestamp - x[1] > timedelta(days=1)])
        
    [stale_up_client_list.append(x) for x in stale_all_client_list if not client_ping_dict[x.id]=='N']

    
    cursor.execute("SELECT reports_client.id FROM reports_client, reports_interaction, reports_entries_interactions WHERE reports_client.id = reports_interaction.client_id AND reports_client.current_interaction_id = reports_entries_interactions.interaction_id and reports_entries_interactions.type=%s GROUP BY reports_client.id", [TYPE_MODIFIED])
    modified_client_list = Client.objects.active(timestamp).filter(id__in=[x[0] for x in cursor.fetchall()])

    cursor.execute("SELECT reports_client.id FROM reports_client, reports_interaction, reports_entries_interactions WHERE reports_client.id = reports_interaction.client_id AND reports_client.current_interaction_id = reports_entries_interactions.interaction_id and reports_entries_interactions.type=%s GROUP BY reports_client.id", [TYPE_EXTRA])
    extra_client_list = Client.objects.active(timestamp).filter(id__in=[x[0] for x in cursor.fetchall()])

    if timestamp == 'now':
        timestamp = datetime.now().isoformat('@')

    return {'client_list': client_list,
            'client_interaction_dict':client_interaction_dict,
            'clean_client_list': clean_client_list,
            'bad_client_list': bad_client_list,
            'extra_client_list': extra_client_list,
            'modified_client_list': modified_client_list,
            'stale_up_client_list': stale_up_client_list,
            'stale_all_client_list': stale_all_client_list,
            'down_client_list': down_client_list,
            'timestamp' : timestamp,
            'timestamp_date' : timestamp[:10],
            'timestamp_time' : timestamp[11:19]}
