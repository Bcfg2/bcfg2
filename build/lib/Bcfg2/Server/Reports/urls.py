from django.conf.urls.defaults import *
from django.http import HttpResponsePermanentRedirect

handler500 = 'Bcfg2.Server.Reports.reports.views.server_error'

urlpatterns = patterns('',
    (r'^', include('Bcfg2.Server.Reports.reports.urls'))
)

#urlpatterns += patterns("django.views",
#    url(r"media/(?P<path>.*)$", "static.serve", {
#      "document_root": '/Users/tlaszlo/svn/bcfg2/reports/site_media/',
#    })
#)
