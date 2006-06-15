# Create your views here.
#from django.shortcuts import get_object_or_404, render_to_response
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from brpt.reports.models import Client, Interaction, Bad, Modified, Extra
from datetime import datetime
    

def index(request):
    return render_to_response('index.html')

def client_index(request):
    client_list = Client.objects.all().order_by('name')
    return render_to_response('clients/index.html',{'client_list': client_list})

def client_detail(request, hostname = -1, pk = -1):
    #SETUP error pages for when you specify a client or interaction that doesn't exist
    client = get_object_or_404(Client, name=hostname)
    if(pk == -1):
        interaction = client.interactions.order_by('-timestamp')[0]
    else:
        interaction = client.interactions.get(pk=pk)
        
    return render_to_response('clients/detail.html',{'client': client, 'interaction': interaction})

def display_sys_view(request):
    client_lists = prepare_client_lists(request)
    return render_to_response('displays/sys_view.html', client_lists)

def display_summary(request):
    client_lists = prepare_client_lists(request)
    return render_to_response('displays/summary.html', client_lists)

def display_timing(request):
    #We're going to send a list of dictionaries. Each dictionary will be a row in the table
    #+------+-------+----------------+-----------+---------+----------------+-------+
    #| name | parse | probe download | inventory | install | cfg dl & parse | total |
    #+------+-------+----------------+-----------+---------+----------------+-------+
    client_list = Client.objects.all().order_by('-name')
    stats_list = []
    #if we have stats for a client, go ahead and add it to the list(wrap in TRY)
    for client in client_list:#Go explicitly to an interaction ID! (new item in dictionary)
        performance_items = client.interactions.order_by('-timestamp')[0].performance_items#allow this to be selectable(hist)
        dict_unit = {}
        try:
            dict_unit["name"] = client.name #node name
        except:
            dict_unit["name"] = "n/a"
        try:
            dict_unit["parse"] = performance_items.get(metric="config_parse").value - performance_items.get(metric="config_download").value #parse
        except:
            dict_unit["parse"] = "n/a"
        try:
            dict_unit["probe"] = performance_items.get(metric="probe_upload").value - performance_items.get(metric="start").value #probe
        except:
            dict_unit["probe"] = "n/a"
        try:
            dict_unit["inventory"] = performance_items.get(metric="inventory").value - performance_items.get(metric="initialization").value #inventory
        except:
            dict_unit["inventory"] = "n/a"
        try:
            dict_unit["install"] = performance_items.get(metric="install").value - performance_items.get(metric="inventory").value #install
        except:
            dict_unit["install"] = "n/a"
        try:
            dict_unit["config"] = performance_items.get(metric="config_parse").value - performance_items.get(metric="probe_upload").value#config download & parse
        except:
            dict_unit["config"] = "n/a"
        try:
            dict_unit["total"] = performance_items.get(metric="finished").value - performance_items.get(metric="start").value #total
        except:
            dict_unit["total"] = "n/a"

        #make sure all is formatted as such: #.##
        stats_list.append(dict_unit)


    return render_to_response('displays/timing.html',{'client_list': client_list, 'stats_list': stats_list})

def display_index(request):
    return render_to_response('displays/index.html')

def prepare_client_lists(request):
    client_list = Client.objects.all().order_by('name')#change this to order by interaction's state
    clean_client_list = []
    bad_client_list = []
    extra_client_list = []
    modified_client_list = []
    stale_up_client_list = []
    stale_all_client_list = []
    down_client_list = []
    for client in client_list:#but we need clientlist for more than just this loop
        i = client.interactions.order_by('-timestamp')[0]
#        if i.state == 'good':
        if i.isclean():
            clean_client_list.append(client)
        else:
            bad_client_list.append(client)
        if i.isstale():
            if i.pingable:
                stale_up_client_list.append(client)
                stale_all_client_list.append(client)                
            else:
                stale_all_client_list.append(client)
        if not i.pingable:
            down_client_list.append(client)
        if len(i.modified_items.all()) > 0:
            modified_client_list.append(client)
        if len(i.extra_items.all()) > 0:
            extra_client_list.append(client)

    #if the list is empty set it to None?
    return {'client_list': client_list,
            'clean_client_list': clean_client_list,
            'bad_client_list': bad_client_list,
            'extra_client_list': extra_client_list,
            'modified_client_list': modified_client_list,
            'stale_up_client_list': stale_up_client_list,
            'stale_all_client_list': stale_all_client_list,
            'down_client_list': down_client_list}
