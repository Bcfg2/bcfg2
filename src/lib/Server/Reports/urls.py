from django.conf.urls.defaults import *
from django.http import HttpResponsePermanentRedirect

handler500 = 'Bcfg2.Server.Reports.reports.views.server_error'

from ConfigParser import ConfigParser, NoSectionError, NoOptionError
c = ConfigParser()
c.read(['/etc/bcfg2.conf', '/etc/bcfg2-web.conf'])

# web_prefix should have a trailing slash, but no leading slash
# e.g. web_prefix = bcfg2/
# web_prefix_root is a workaround for the index
if c.has_option('statistics', 'web_prefix'):
    web_prefix = c.get('statistics', 'web_prefix').lstrip('/')
else:
    web_prefix = ''

urlpatterns = patterns('',
    (r'^%s' % web_prefix, include('Bcfg2.Server.Reports.reports.urls'))
)

urlpatterns += patterns("django.views",
    url(r"media/(?P<path>.*)$", "static.serve", {
      "document_root": '/Users/tlaszlo/svn/bcfg2/reports/site_media/',
    })
)
