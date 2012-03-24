from django.contrib import admin

from models import Host, Interface, IP, MX, Name, CName, Nameserver, ZoneAddress, Zone, Log, ZoneLog

admin.site.register(Host)
admin.site.register(Interface)
admin.site.register(IP)
admin.site.register(MX)
admin.site.register(Name)
admin.site.register(CName)
admin.site.register(Nameserver)
admin.site.register(ZoneAddress)
admin.site.register(Zone)
admin.site.register(Log)
admin.site.register(ZoneLog)
