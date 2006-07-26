# Create your views here.
#from django.shortcuts import get_object_or_404, render_to_response
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from brpt.reports.models import Client, Interaction, Bad, Modified, Extra, Performance, Reason
from datetime import datetime, timedelta
from time import strptime
from django.db import connection    

def index(request):
    return render_to_response('index.html')

def config_item_modified(request, eyedee =None, timestamp = 'now'):
    #if eyedee = None, dump with a 404
    timestamp = timestamp.replace("@"," ")
    mod_or_bad = "modified"
    
    item = Modified.objects.get(id=eyedee)
    #if everything is blank except current_exists, do something special
    cursor = connection.cursor()
    if timestamp == 'now':
        cursor.execute("select client_id from reports_interaction, reports_modified_interactions, reports_client "+
                   "WHERE reports_client.current_interaction_id = reports_modified_interactions.interaction_id "+
                   "AND reports_modified_interactions.interaction_id = reports_interaction.id "+
                   "AND reports_modified_interactions.modified_id = %s", [eyedee])
        associated_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall()])
    else:
        interact_queryset = Interaction.objects.interaction_per_client(timestamp)
        interactionlist = []
        [interactionlist.append(x.id) for x in interact_queryset]
        if not interactionlist == []:
            cursor.execute("select client_id from reports_interaction, reports_modified_interactions, reports_client "+
                   "WHERE reports_modified_interactions.interaction_id IN %s "+
                   "AND reports_modified_interactions.interaction_id = reports_interaction.id "+
                   "AND reports_modified_interactions.modified_id = %s", [interactionlist, eyedee])
            associated_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall()])
        else:
            associated_client_list = []

    if timestamp == 'now':
        timestamp = datetime.now().isoformat('@')

    for q in connection.queries:
        print q

    return render_to_response('config_items/index.html',{'item':item,
                                                         'mod_or_bad':mod_or_bad,
                                                         'associated_client_list':associated_client_list,
                                                         'timestamp' : timestamp,
                                                         'timestamp_date' : timestamp[:10],
                                                         'timestamp_time' : timestamp[11:19]})
                                                    

def config_item_bad(request, eyedee = None, timestamp = 'now'):
    timestamp = timestamp.replace("@"," ")
    mod_or_bad = "bad"
    item = Bad.objects.get(id=eyedee)
    cursor = connection.cursor()
    if timestamp == 'now':
        cursor.execute("select client_id from reports_interaction, reports_bad_interactions, reports_client "+
                   "WHERE reports_client.current_interaction_id = reports_bad_interactions.interaction_id "+
                   "AND reports_bad_interactions.interaction_id = reports_interaction.id "+
                   "AND reports_bad_interactions.bad_id = %s", [eyedee])
        associated_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall()])
    else:
        interact_queryset = Interaction.objects.interaction_per_client(timestamp)
        interactionlist = []
        [interactionlist.append(x.id) for x in interact_queryset]
        if not interactionlist == []:
            cursor.execute("select client_id from reports_interaction, reports_bad_interactions, reports_client "+
                           "WHERE reports_bad_interactions.interaction_id IN %s "+
                           "AND reports_bad_interactions.interaction_id = reports_interaction.id "+
                           "AND reports_bad_interactions.bad_id = %s", [interactionlist, eyedee])
            associated_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall()])
        else:
            associated_client_list = None

    if timestamp == 'now':
        timestamp = datetime.now().isoformat('@')


    for q in connection.queries:
        print q

    return render_to_response('config_items/index.html',{'item':item,
                                                         'mod_or_bad':mod_or_bad,
                                                         'associated_client_list':associated_client_list,
                                                         'timestamp' : timestamp,
                                                         'timestamp_date' : timestamp[:10],
                                                         'timestamp_time' : timestamp[11:19]})



def client_index(request):
    client_list = Client.objects.all().order_by('name')
    client_list_a = client_list[:len(client_list)/2]
    client_list_b = client_list[len(client_list)/2:]
    return render_to_response('clients/index.html',{'client_list_a': client_list_a,
                                                    'client_list_b': client_list_b})

def client_detail(request, hostname = None, pk = None):
    #SETUP error pages for when you specify a client or interaction that doesn't exist
    client = get_object_or_404(Client, name=hostname)
    if(pk == None):
        interaction = client.current_interaction
    else:
        interaction = client.interactions.get(pk=pk)#can this be a get object or 404?

    #for q in connection.queries:
    #    print q

    return render_to_response('clients/detail.html',{'client': client, 'interaction': interaction})

def display_sys_view(request, timestamp = 'now'):
    client_lists = prepare_client_lists(request, timestamp)

    #for q in connection.queries:
    #    print q


    return render_to_response('displays/sys_view.html', client_lists)

def display_summary(request, timestamp = 'now'):
    
    client_lists = prepare_client_lists(request, timestamp)
    #this returns timestamp and the timestamp parts too
    
    #for q in connection.queries:
    #    print q

    return render_to_response('displays/summary.html', client_lists)

def display_timing(request, timestamp = 'now'):
    #We're going to send a list of dictionaries. Each dictionary will be a row in the table
    #+------+-------+----------------+-----------+---------+----------------+-------+
    #| name | parse | probe download | inventory | install | cfg dl & parse | total |
    #+------+-------+----------------+-----------+---------+----------------+-------+
    client_list = Client.objects.all().order_by('name')
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
            dict_unit["parse"] = round(d["config_parse"] - d["config_download"],4) #parse
        except:
            dict_unit["parse"] = "n/a"
        try:
            dict_unit["probe"] = round(d["probe_upload"] - d["start"],4) #probe
        except:
            dict_unit["probe"] = "n/a"
        try:
            dict_unit["inventory"] = round(d["inventory"] - d["initialization"],4) #inventory
        except:
            dict_unit["inventory"] = "n/a"
        try:
            dict_unit["install"] = round(d["install"] - d["inventory"],4) #install
        except:
            dict_unit["install"] = "n/a"
        try:
            dict_unit["config"] = round(d["config_parse"] - d["probe_upload"],4)#config download & parse
        except:
            dict_unit["config"] = "n/a"
        try:
            dict_unit["total"] = round(d["finished"] - d["start"],4) #total
        except:
            dict_unit["total"] = "n/a"

        stats_list.append(dict_unit)

    return render_to_response('displays/timing.html',{'client_list': client_list,
                                                      'stats_list': stats_list,
                                                      'timestamp' : timestamp,
                                                      'timestamp_date' : timestamp[:10],
                                                      'timestamp_time' : timestamp[11:19]})

def display_index(request):
    return render_to_response('displays/index.html')

def prepare_client_lists(request, timestamp = 'now'):
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
    [client_interaction_dict.__setitem__(x.client_id,x) for x in interact_queryset]
    client_list = Client.objects.filter(id__in=client_interaction_dict.keys()).order_by('name')

    [clean_client_list.append(x) for x in Client.objects.filter(id__in=[y.client_id for y in interact_queryset.filter(state='clean')])]
    [bad_client_list.append(x) for x in Client.objects.filter(id__in=[y.client_id for y in interact_queryset.filter(state='dirty')])]
    [down_client_list.append(x) for x in Client.objects.filter(id__in=[y.client_id for y in interact_queryset.filter(pingable='N')])]#need to change the PINGING data structure

    if (timestamp == 'now' or timestamp == None): 
        cursor.execute("select client_id, MAX(timestamp) as timestamp from reports_interaction GROUP BY client_id")
        stale_all_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall() if datetime.now() - x[1]>timedelta(days=1)])
    else:
        cursor.execute("select client_id, timestamp, MAX(timestamp) as timestamp from reports_interaction "+
                       "WHERE timestamp < %s GROUP BY client_id", [timestamp])
        t = strptime(timestamp,"%Y-%m-%d %H:%M:%S")
        datetimestamp = datetime(t[0],t[1],t[2],t[3],t[4],t[5])
        stale_all_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall() if datetimestamp - x[1] > timedelta(days=1)])
        
    [stale_up_client_list.append(x) for x in stale_all_client_list if client_interaction_dict[x.id].pingable=='Y']

    
    cursor.execute("SELECT reports_client.id FROM reports_client, reports_interaction, reports_modified_interactions WHERE reports_client.id=reports_interaction.client_id AND reports_interaction.id = reports_modified_interactions.interaction_id GROUP BY reports_client.id")
    modified_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall()])

    cursor.execute("SELECT reports_client.id FROM reports_client, reports_interaction, reports_extra_interactions WHERE reports_client.id=reports_interaction.client_id AND reports_interaction.id = reports_extra_interactions.interaction_id GROUP BY reports_client.id")
    extra_client_list = Client.objects.filter(id__in=[x[0] for x in cursor.fetchall()])

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
