from django.conf.urls.defaults import *
from django.core.urlresolvers import reverse, NoReverseMatch
from django.http import HttpResponsePermanentRedirect
from Bcfg2.Reporting.utils import filteredUrls, paginatedUrls, timeviewUrls

handler500 = 'Bcfg2.Reporting.views.server_error'

def newRoot(request):
    try:
        grid_view = reverse('reports_grid_view')
    except NoReverseMatch:
        grid_view = '/grid'
    return HttpResponsePermanentRedirect(grid_view)

urlpatterns = patterns('Bcfg2.Reporting',
    (r'^$', newRoot),

    url(r'^manage/?$', 'views.client_manage', name='reports_client_manage'),
    url(r'^client/(?P<hostname>[^/]+)/(?P<pk>\d+)/?$', 'views.client_detail', name='reports_client_detail_pk'),
    url(r'^client/(?P<hostname>[^/]+)/?$', 'views.client_detail', name='reports_client_detail'),
    url(r'^element/(?P<entry_type>\w+)/(?P<pk>\d+)/(?P<interaction>\d+)?/?$', 'views.config_item', name='reports_item'),
    url(r'^element/(?P<entry_type>\w+)/(?P<pk>\d+)/?$', 'views.config_item', name='reports_item'),
    url(r'^entry/(?P<entry_type>\w+)/(?P<pk>\w+)/?$', 'views.entry_status', name='reports_entry'),
)

urlpatterns += patterns('Bcfg2.Reporting',
    *timeviewUrls(
        (r'^summary/?$', 'views.display_summary', None, 'reports_summary'),
        (r'^timing/?$', 'views.display_timing', None, 'reports_timing'),
        (r'^common/group/(?P<group>[^/]+)/(?P<threshold>\d+)/?$', 'views.common_problems', None, 'reports_common_problems'),
        (r'^common/group/(?P<group>[^/]+)+/?$', 'views.common_problems', None, 'reports_common_problems'),
        (r'^common/(?P<threshold>\d+)/?$', 'views.common_problems', None, 'reports_common_problems'),
        (r'^common/?$', 'views.common_problems', None, 'reports_common_problems'),
))

urlpatterns += patterns('Bcfg2.Reporting',
    *filteredUrls(*timeviewUrls(
        (r'^grid/?$', 'views.client_index', None, 'reports_grid_view'),
        (r'^detailed/?$',
            'views.client_detailed_list', None, 'reports_detailed_list'),
        (r'^elements/(?P<item_state>\w+)/?$', 'views.config_item_list', None, 'reports_item_list'),
)))

urlpatterns += patterns('Bcfg2.Reporting',
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

