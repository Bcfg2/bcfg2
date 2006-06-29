from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^brpt/', include('brpt.apps.foo.urls.foo')),
    (r'^/*$','brpt.reports.views.index'),
    (r'^clients/(?P<hostname>\S+)/(?P<pk>\d+)/$', 'brpt.reports.views.client_detail'),
    (r'^clients/(?P<hostname>\S+)/$', 'brpt.reports.views.client_detail'),
    (r'^clients/(?P<hostname>\S+)$', 'brpt.reports.views.client_detail'),
                       #hack because hostnames have periods and we still want to append slash
    (r'^clients/$','brpt.reports.views.client_index'),

    (r'^displays/sys-view/$','brpt.reports.views.display_sys_view'),
    (r'^displays/summary/$','brpt.reports.views.display_summary'),
    (r'^displays/timing/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','brpt.reports.views.display_timing'),
    (r'^displays/timing/$','brpt.reports.views.display_timing'),                       
    (r'^displays/$','brpt.reports.views.display_index'),

    # Uncomment this for admin:
    (r'^admin/', include('django.contrib.admin.urls')),




    #Remove this when not doing DEVELOPMENT
    #and i quote:
    #Using this method is inefficient and insecure. Do not use this in a production setting. Use this only for development.
    (r'^site_media/(.*)$', 'django.views.static.serve', {'document_root': '/Users/joey/anl-mcs/dev/bcfg2/reports/site_media/'}),


)
