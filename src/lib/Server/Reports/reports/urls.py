from django.conf.urls.defaults import *
from django.core.urlresolvers import reverse, NoReverseMatch
from django.http import HttpResponsePermanentRedirect
from Bcfg2.Server.Reports.utils import filteredUrls, paginatedUrls, timeviewUrls

def newRoot(request):
    try:
        grid_view = reverse('reports_grid_view')
    except NoReverseMatch:
        grid_view = '/grid'
    return HttpResponsePermanentRedirect(grid_view)

urlpatterns = patterns('Bcfg2.Server.Reports.reports',
    (r'^$', newRoot),

    url(r'^manage/?$', 'views.client_manage', name='reports_client_manage'),
    url(r'^client/(?P<hostname>[^/]+)/(?P<pk>\d+)/?$', 'views.client_detail', name='reports_client_detail_pk'),
    url(r'^client/(?P<hostname>[^/]+)/?$', 'views.client_detail', name='reports_client_detail'),
    url(r'^elements/(?P<type>\w+)/(?P<pk>\d+)/?$', 'views.config_item', name='reports_item'),
)

urlpatterns += patterns('Bcfg2.Server.Reports.reports',
    *timeviewUrls(
        (r'^grid/?$', 'views.client_index', None, 'reports_grid_view'),
        (r'^summary/?$', 'views.display_summary', None, 'reports_summary'),
        (r'^timing/?$', 'views.display_timing', None, 'reports_timing'),
        (r'^elements/(?P<type>\w+)/?$', 'views.config_item_list', None, 'reports_item_list'),
))

urlpatterns += patterns('Bcfg2.Server.Reports.reports',
    *filteredUrls(*timeviewUrls(
        (r'^detailed/?$',
            'views.client_detailed_list', None, 'reports_detailed_list')
)))

urlpatterns += patterns('Bcfg2.Server.Reports.reports',
    *paginatedUrls( *filteredUrls(
        (r'^history/?$',
            'views.render_history_view', None, 'reports_history'),
        (r'^history/(?P<hostname>[^/|]+)/?$',
            'views.render_history_view', None, 'reports_client_history'),
)))

    # Uncomment this for admin:
    #(r'^admin/', include('django.contrib.admin.urls')),


## Uncomment this section if using authentication
#urlpatterns += patterns('',
#                        (r'^login/$', 'django.contrib.auth.views.login',
#                         {'template_name': 'auth/login.html'}),
#                        (r'^logout/$', 'django.contrib.auth.views.logout',
#                         {'template_name': 'auth/logout.html'})
#                        )

