from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^Bcfg2.Server.Reports/', include('Bcfg2.Server.Reports.apps.foo.urls.foo')),
    (r'^/*$','Bcfg2.Server.Reports.reports.views.index'),
    (r'^clients/(?P<hostname>\S+)/(?P<pk>\d+)/$', 'Bcfg2.Server.Reports.reports.views.client_detail'),
    (r'^clients/(?P<hostname>\S+)/$', 'Bcfg2.Server.Reports.reports.views.client_detail'),
    (r'^clients/(?P<hostname>\S+)$', 'Bcfg2.Server.Reports.reports.views.client_detail'),
                       #hack because hostnames have periods and we still want to append slash
    (r'^clients/$','Bcfg2.Server.Reports.reports.views.client_index'),
    (r'^displays/sys-view/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.display_sys_view'),
    (r'^displays/sys-view/$','Bcfg2.Server.Reports.reports.views.display_sys_view'),
    (r'^displays/summary/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.display_summary'),
    (r'^displays/summary/$','Bcfg2.Server.Reports.reports.views.display_summary'),
    (r'^displays/timing/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.display_timing'),
    (r'^displays/timing/$','Bcfg2.Server.Reports.reports.views.display_timing'),
    (r'^displays/$','Bcfg2.Server.Reports.reports.views.display_index'),

    (r'^elements/modified/(?P<eyedee>\d+)/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.config_item_modified'),
    (r'^elements/modified/(?P<eyedee>\d+)/$','Bcfg2.Server.Reports.reports.views.config_item_modified'),
    (r'^elements/modified/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01]\
    [0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.modified_item_index'),
    (r'^elements/modified/$','Bcfg2.Server.Reports.reports.views.modified_item_index'),
    (r'^elements/bad/(?P<eyedee>\d+)/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.config_item_bad'),
    (r'^elements/bad/(?P<eyedee>\d+)/$','Bcfg2.Server.Reports.reports.views.config_item_bad'),
    (r'^elements/bad/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01]\
    [0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$','Bcfg2.Server.Reports.reports.views.bad_item_index'),
    (r'^elements/bad/$','Bcfg2.Server.Reports.reports.views.bad_item_index'),
)

    # Uncomment this for admin:
    #(r'^admin/', include('django.contrib.admin.urls')),


## Uncomment this section if using authentication
#urlpatterns += patterns('',
#                        (r'^login/$', 'django.contrib.auth.views.login',
#                         {'template_name': 'auth/login.html'}),
#                        (r'^logout/$', 'django.contrib.auth.views.logout',
#                         {'template_name': 'auth/logout.html'})
#                        )
