from django.conf.urls.defaults import *

urlpatterns = patterns('Bcfg2.Server.Hostbase.hostbase.views',
                       
                       (r'^admin/', include('django.contrib.admin.urls')),
                       (r'^hostbase/$', 'search'),
                       (r'^$','index' ),
                       (r'^hostbase/(?P<host_id>\d+)/$', 'look'),
                       (r'^hostbase/(?P<host_id>\d+)/edit', 'edit'),
                       (r'^hostbase/(?P<host_id>\d+)/remove', 'remove'),
                       (r'^hostbase/(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
                       (r'^hostbase/(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/(?P<name_id>\d+)/confirm', 'confirm'),
                       (r'^hostbase/(?P<host_id>\d+)/dns/edit', 'dnsedit'),
                       (r'^hostbase/(?P<host_id>\d+)/dns', 'dns'),
                       (r'^hostbase/(?P<host_id>\d+)/logs/(?P<log_id>\d+)', 'printlog'),
                       (r'^hostbase/(?P<host_id>\d+)/logs', 'logs'),
                       (r'^hostbase/new', 'new'),
                       (r'^hostbase/(?P<host_id>\d+)/copy', 'copy'),
                       (r'^hostbase/hostinfo', 'hostinfo'),
                       (r'^hostbase/zones/$', 'zones'),
                       (r'^hostbase/zones/(?P<zone_id>\d+)/$', 'zoneview'),                       
                       (r'^hostbase/zones/(?P<zone_id>\d+)/edit', 'zoneedit'),
                       (r'^hostbase/zones/new/$', 'zonenew'),
                       (r'^hostbase/zones/(?P<zone_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
                       )

urlpatterns += patterns('',                        
                        (r'^login/$', 'django.contrib.auth.views.login',
                         {'template_name': 'login.html'}),
                        (r'^logout/$', 'django.contrib.auth.views.logout',
                         {'template_name': 'logout.html'})
                        )
                       
