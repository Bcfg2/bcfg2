from django.conf.urls.defaults import *

urlpatterns = patterns('Hostbase.hostbase.views',
    # Example:
    # (r'^djangobase/', include('djangobase.apps.foo.urls.foo')),

    # Uncomment this for admin:
    (r'^admin/', include('django.contrib.admin.urls')),
    (r'^hostbase/$', 'search'),
    (r'^hostbase/(?P<host_id>\d+)/$', 'look'),
    (r'^hostbase/(?P<host_id>\d+)/edit', 'edit'),
    (r'^hostbase/(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/confirm', 'confirm'),
    (r'^hostbase/(?P<host_id>\d+)/(?P<item>\D+)/(?P<item_id>\d+)/(?P<name_id>\d+)/confirm', 'confirm'),
    (r'^hostbase/(?P<host_id>\d+)/dns/edit', 'dnsedit'),
    (r'^hostbase/(?P<host_id>\d+)/dns', 'dns'),
    (r'^hostbase/new', 'new'),
    (r'^hostbase/hostinfo', 'hostinfo'),
    (r'^hostbase/zones', 'zones'),                       
)
