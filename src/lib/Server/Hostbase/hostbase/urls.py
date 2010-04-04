# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.core.urlresolvers import reverse

from models import Host, Zone

host_detail_dict = {
    'queryset':Host.objects.all(),
    'template_name':'host.html',
    'template_object_name':'host',
}

zone_new_dict = {
    'model':Zone,
    'template_name':'zonenew.html',
    'post_save_redirect':'/hostbase/zones',
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

urlpatterns = patterns('django.views.generic.list_detail',
    (r'^(?P<object_id>\d+)/$', 'object_detail', host_detail_dict, 'host_detail'),
    (r'^zones/$', 'object_list', zones_list_dict, 'zone_list'),
    (r'^zones/(?P<object_id>\d+)/$', 'object_detail', zone_detail_dict, 'zone_detail'),
)

urlpatterns += patterns('django.views.generic.create_update',
    (r'^zones/new/$', 'create_object', zone_new_dict, 'zone_new'),
    (r'^zones/(?P<object_id>\d+)/edit', 'update_object', zone_new_dict, 'zone_edit'),
)

urlpatterns += patterns('Bcfg2.Server.Hostbase.hostbase.views',
                       (r'^$', 'search'),
                       (r'^(?P<host_id>\d+)/edit', 'edit'),
                       (r'^(?P<host_id>\d+)/remove', 'remove'),
                       (r'^(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
                       (r'^(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/(?P<name_id>\d+)/confirm', 'confirm'),
                       (r'^(?P<host_id>\d+)/dns/edit', 'dnsedit'),
                       (r'^(?P<host_id>\d+)/dns', 'dns'),
                       (r'^(?P<host_id>\d+)/logs/(?P<log_id>\d+)', 'printlog'),
                       (r'^(?P<host_id>\d+)/logs', 'logs'),
                       (r'^new', 'new'),
                       (r'^(?P<host_id>\d+)/copy', 'copy'),
#                       (r'^hostinfo', 'hostinfo'),
                       (r'^zones/(?P<zone_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
                       )
