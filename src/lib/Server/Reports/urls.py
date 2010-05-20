from django.conf.urls.defaults import *

from ConfigParser import ConfigParser, NoSectionError, NoOptionError
c = ConfigParser()
c.read(['/etc/bcfg2.conf', '/etc/bcfg2-web.conf'])

# web_prefix should have a trailing slash, but no leading slash
# e.g. web_prefix = bcfg2/
# web_prefix_root is a workaround for the index
if c.has_option('statistics', 'web_prefix'):
    web_prefix = c.get('statistics', 'web_prefix').lstrip('/')
    web_prefix_root = web_prefix
else:
    web_prefix = ''
    web_prefix_root = '/'

urlpatterns = patterns('',
    # Example:
    # (r'^%sBcfg2.Server.Reports/' % web_prefix, include('Bcfg2.Server.Reports.apps.foo.urls.foo')),
    (r'^%s*$' % web_prefix_root,'Bcfg2.Server.Reports.reports.views.index'),

    (r'^%sclients-detailed/state/(?P<state>\w+)/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_detailed_list'),
    (r'^%sclients-detailed/server/(?P<server>[\w\-\.]+)/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_detailed_list'),
    (r'^%sclients-detailed/server/(?P<server>[\w\-\.]+)/(?P<state>[A-Za-z]+)/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_detailed_list'),
    (r'^%sclients-detailed/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_detailed_list'),
    (r'^%sclients/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_index'),
    (r'^%sclients/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_index'),
    (r'^%sclients/(?P<hostname>\S+)/(?P<pk>\d+)/$' % web_prefix, 'Bcfg2.Server.Reports.reports.views.client_detail'),
    (r'^%sclients/(?P<hostname>\S+)/manage/$' % web_prefix, 'Bcfg2.Server.Reports.reports.views.client_manage'),
    (r'^%sclients/(?P<hostname>\S+)/$' % web_prefix, 'Bcfg2.Server.Reports.reports.views.client_detail'),
    (r'^%sclients/(?P<hostname>\S+)$' % web_prefix, 'Bcfg2.Server.Reports.reports.views.client_detail'),
                       #hack because hostnames have periods and we still want to append slash
    (r'^%sclients/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.client_index'),
    (r'^%sdisplays/sys-view/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_sys_view'),
    (r'^%sdisplays/sys-view/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_sys_view'),
    (r'^%sdisplays/summary/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_summary'),
    (r'^%sdisplays/summary/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_summary'),
    (r'^%sdisplays/timing/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_timing'),
    (r'^%sdisplays/timing/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_timing'),
    (r'^%sdisplays/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.display_index'),

    (r'^%selements/modified/(?P<eyedee>\d+)/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.config_item_modified'),
    (r'^%selements/modified/(?P<eyedee>\d+)/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.config_item_modified'),
    (r'^%selements/modified/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01]\
    [0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.modified_item_index'),
    (r'^%selements/modified/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.modified_item_index'),
    (r'^%selements/bad/(?P<eyedee>\d+)/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01][0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.config_item_bad'),
    (r'^%selements/bad/(?P<eyedee>\d+)/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.config_item_bad'),
    (r'^%selements/bad/(?P<timestamp>(19|20)\d\d-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])@([01]\
    [0-9]|2[0-3]):([0-5][0-9]|60):([0-5][0-9]|60))/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.bad_item_index'),
    (r'^%selements/bad/$' % web_prefix,'Bcfg2.Server.Reports.reports.views.bad_item_index'),
)

    # Uncomment this for admin:
    #(r'^%sadmin/' % web_prefix, include('django.contrib.admin.urls')),


## Uncomment this section if using authentication
#urlpatterns += patterns('',
#                        (r'^%slogin/$' % web_prefix, 'django.contrib.auth.views.login',
#                         {'template_name': 'auth/login.html'}),
#                        (r'^%slogout/$' % web_prefix, 'django.contrib.auth.views.logout',
#                         {'template_name': 'auth/logout.html'})
#                        )
