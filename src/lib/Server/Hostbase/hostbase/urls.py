# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.views.generic.create_update import create_object, update_object, delete_object
from django.views.generic.list_detail import object_detail, object_list

from models import Host, Zone, Log

host_detail_dict = {
    'queryset':Host.objects.all(),
    'template_name':'host.html',
    'template_object_name':'host',
}

host_delete_dict = {
    'model':Host,
    'post_delete_redirect':'/',
}

host_log_detail_dict = host_detail_dict.copy()
host_log_detail_dict['template_name'] = 'logviewer.html'

host_dns_detail_dict = host_detail_dict.copy()
host_dns_detail_dict['template_name'] = 'dns.html'

zone_new_dict = {
    'model':Zone,
    'template_name':'zonenew.html',
    'post_save_redirect':'../%(id)s',
}

zones_list_dict = {
    'queryset':Zone.objects.all(),
    'template_name':'zones.html',
    'template_object_name':'zone',
}

zone_detail_dict = {
    'queryset':Zone.objects.all(),
    'template_name':'zoneview.html',
    'template_object_name':'zone',
}

urlpatterns = patterns('',
    (r'^(?P<object_id>\d+)/$', object_detail, host_detail_dict, 'host_detail'),
    (r'^zones/new/$', login_required(create_object), zone_new_dict, 'zone_new'),
    (r'^zones/(?P<object_id>\d+)/edit', login_required(update_object), zone_new_dict, 'zone_edit'),
    (r'^zones/$', object_list, zones_list_dict, 'zone_list'),
    (r'^zones/(?P<object_id>\d+)/$', object_detail, zone_detail_dict, 'zone_detail'),
    (r'^zones/(?P<object_id>\d+)/$', object_detail, zone_detail_dict, 'zone_detail'),
    (r'^\d+/logs/(?P<object_id>\d+)/', object_detail, { 'queryset':Log.objects.all() }, 'log_detail'),
    (r'^(?P<object_id>\d+)/logs/', object_detail, host_log_detail_dict, 'host_log_list'),
    (r'^(?P<object_id>\d+)/dns', object_detail, host_dns_detail_dict, 'host_dns_list'),
    (r'^(?P<object_id>\d+)/remove', login_required(delete_object), host_delete_dict, 'host_delete'),
)

urlpatterns += patterns('Bcfg2.Server.Hostbase.hostbase.views',
    (r'^$', 'search'),
    (r'^(?P<host_id>\d+)/edit', 'edit'),
    (r'^(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
    (r'^(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/(?P<name_id>\d+)/confirm', 'confirm'),
    (r'^(?P<host_id>\d+)/dns/edit', 'dnsedit'),
    (r'^new', 'new'),
    (r'^(?P<host_id>\d+)/copy', 'copy'),
#   (r'^hostinfo', 'hostinfo'),
    (r'^zones/(?P<zone_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
)
