import os
from django.conf.urls.defaults import *

urlpatterns = patterns('Hostbase.hostbase.views',
                       
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
                       (r'^hostbase/new', 'new'),
                       (r'^hostbase/hostinfo', 'hostinfo'),
                       (r'^hostbase/zones/$', 'zones'),
                       (r'^hostbase/zones/(?P<zone_id>\d+)/$', 'zoneview'),                       
                       (r'^hostbase/zones/(?P<zone_id>\d+)/edit', 'zoneedit'),
                       (r'^hostbase/zones/new/$', 'zonenew'),
                       (r'^hostbase/zones/(?P<zone_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
                       )

#fixme: this is a temp. kludge to handle static serving of css, img, js etc...
#a better solution is to use mod_python/apache directives for the static serving
os.environ['bcfg_media_root'] = '/usr/lib/python2.4/site-packages/Hostbase/media'

urlpatterns += patterns('',
                        (r'^site_media/(.*)$',
                         'django.views.static.serve',
                         {'document_root': os.environ['bcfg_media_root'],
                          'show_indexes': True}),
                        )
urlpatterns += patterns('',                        
                        (r'^login/$', 'django.contrib.auth.views.login',
                         {'template_name': 'login.html'}),
                        (r'^logout/$', 'django.contrib.auth.views.logout',
                         {'template_name': 'logout.html'})
                        )
                       
