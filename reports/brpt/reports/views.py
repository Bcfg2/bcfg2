# Create your views here.
#from django.shortcuts import get_object_or_404, render_to_response
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from brpt.reports.models import Client, Interaction, Bad, Modified, Extra, Performance
from datetime import datetime
    

def index(request):
    return render_to_response('index.html')

def client_index(request):
    client_list = Client.objects.all().order_by('name')
    return render_to_response('clients/index.html',{'client_list': client_list})

def client_detail(request, hostname = None, pk = None):
    #SETUP error pages for when you specify a client or interaction that doesn't exist
    client = get_object_or_404(Client, name=hostname)
    if(pk == None):
        interaction = client.current_interaction
    else:
        interaction = client.interactions.get(pk=pk)#can this be a get object or 404?

    return render_to_response('clients/detail.html',{'client': client, 'interaction': interaction})

def display_sys_view(request):
    client_lists = prepare_client_lists(request)

    from django.db import connection
    for q in connection.queries:
        print q


    return render_to_response('displays/sys_view.html', client_lists)

def display_summary(request):
    client_lists = prepare_client_lists(request)

    from django.db import connection
    for q in connection.queries:
        print q

    return render_to_response('displays/summary.html', client_lists)

def display_timing(request, timestamp = None):
    #We're going to send a list of dictionaries. Each dictionary will be a row in the table
    #+------+-------+----------------+-----------+---------+----------------+-------+
    #| name | parse | probe download | inventory | install | cfg dl & parse | total |
    #+------+-------+----------------+-----------+---------+----------------+-------+
    client_list = Client.objects.all().order_by('name')
    stats_list = []
    #Try to parse timestamp, if it has an @ symbol, replace it with a space and pass it.
    #sanity check it too.
    #else, justcall it with nothing....
    #use a popup calendar !
    results = Performance.objects.performance_per_client('2006-07-07 00:00:00')

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

        #make sure all is formatted as such: #.##
        stats_list.append(dict_unit)



    from django.db import connection
    for q in connection.queries:
        print q






    return render_to_response('displays/timing.html',{'client_list': client_list, 'stats_list': stats_list})

def display_index(request):
    return render_to_response('displays/index.html')

def prepare_client_lists(request):
    client_list = Client.objects.all().order_by('name')#change this to order by interaction's state
    client_interaction_dict = {}
    clean_client_list = []
    bad_client_list = []
    extra_client_list = []
    modified_client_list = []
    stale_up_client_list = []
    stale_all_client_list = []
    down_client_list = []

    [client_interaction_dict.__setitem__(x.client_id,x) for x in Interaction.objects.interaction_per_client('now')]# or you can specify a time like this: '2007-01-01 00:00:00'
    
    for client in client_list:
        #i = client_interaction_dict[client.id]

        if client_interaction_dict[client.id].isclean():
            clean_client_list.append(client)
        else:
            bad_client_list.append(client)
        if client_interaction_dict[client.id].isstale():
            if client_interaction_dict[client.id].pingable:
                stale_up_client_list.append(client)
                stale_all_client_list.append(client)                
            else:
                stale_all_client_list.append(client)
        if not client_interaction_dict[client.id].pingable:
            down_client_list.append(client)
        
        if len(client_interaction_dict[client.id].modified_items.all()) > 0:
            modified_client_list.append(client)
        if len(client_interaction_dict[client.id].extra_items.all()) > 0:
            extra_client_list.append(client)

    #if the list is empty set it to None?
    return {'client_list': client_list,
            'client_interaction_dict':client_interaction_dict,
            'clean_client_list': clean_client_list,
            'bad_client_list': bad_client_list,
            'extra_client_list': extra_client_list,
            'modified_client_list': modified_client_list,
            'stale_up_client_list': stale_up_client_list,
            'stale_all_client_list': stale_all_client_list,
            'down_client_list': down_client_list}
