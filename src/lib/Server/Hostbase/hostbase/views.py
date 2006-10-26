"""Views.py
Contains all the views associated with the hostbase app
Also has does form validation
"""
__revision__ = "$Revision: $"

from django.http import HttpResponse, HttpResponseRedirect

from django.contrib.auth.decorators import login_required

from Hostbase.hostbase.models import *
from datetime import date
from django.db import connection
from django.shortcuts import render_to_response
from Hostbase import settings, regex
import re
    
attribs = ['hostname', 'whatami', 'netgroup', 'security_class', 'support',
           'csi', 'printq', 'primary_user', 'administrator', 'location',
           'status']

zoneattribs = ['zone', 'admin', 'primary_master', 'expire', 'retry',
               'refresh', 'ttl', 'aux']

dispatch = {'mac_addr':'i.mac_addr LIKE \'%%%%%s%%%%\'',
            'ip_addr':'p.ip_addr LIKE \'%%%%%s%%%%\'',
            'name':'n.name LIKE \'%%%%%s%%%%\'',
            'cname':'c.cname LIKE \'%%%%%s%%%%\'',
            'mx':'m.mx LIKE \'%%%%%s%%%%\'',
            'dns_view':'n.dns_view = \'%s\'',
            'hdwr_type':'i.hdwr_type = \'%s\''}


## def netreg(request):
##     if request.GET.has_key('sub'):
##         failures = []
##         validated = True
##         # do validation right in here
##         macaddr_regex = re.compile('^[0-9abcdef]{2}(:[0-9abcdef]{2}){5}$')
##         if not (request.POST['mac_addr'] and macaddr_regex.match(request.POST['mac_addr'])):
##             validated = False
##         userregex = re.compile('^[a-z0-9-_\.@]+$')
##         if not (request.POST['email_address'] and userregex.match(request.POST['email_address'])):
##             validated = False
##         if not validated:
##             t = Template(open('./hostbase/webtemplates/errors.html').read())
##             t.failures = validate(request, True)
##             return HttpResponse(str(t))
##         return HttpResponseRedirect('/hostbase/%s/' % host.id)
##     else:
##         t = Template(open('./hostbase/webtemplates/netreg.html').read())
##         t.TYPE_CHOICES = Interface.TYPE_CHOICES
##         t.failures = False
##         return HttpResponse(str(t))
    
def login(request):
    return render_to_response('login.html', {'next':'/hostbase'})
        

def search(request):
    """Search for hosts in the database
    If more than one field is entered, logical AND is used
    """
    if request.GET.has_key('sub'):
        querystring = """SELECT DISTINCT h.hostname, h.id, h.status
        FROM (((((hostbase_host h
        INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id)
        INNER JOIN hostbase_name n ON p.id = n.ip_id)
        INNER JOIN hostbase_name_mxs x ON n.id = x.name_id)
        INNER JOIN hostbase_mx m ON m.id = x.mx_id)
        LEFT JOIN hostbase_cname c ON n.id = c.name_id
        WHERE """

        _and = False
        for field in request.POST:
            if request.POST[field] and field in dispatch:
                if _and:
                    querystring += ' AND '
                querystring += dispatch[field]  % request.POST[field]
                _and = True
            elif request.POST[field]:
                if _and:
                    querystring += ' AND '
                querystring += "h.%s LIKE \'%%%%%s%%%%\'" % (field, request.POST[field])
                _and = True
               
        if not _and:
            cursor = connection.cursor()
            cursor.execute("""SELECT hostname, id, status
            FROM hostbase_host ORDER BY hostname""")
            results = cursor.fetchall()
        else:
            querystring += " ORDER BY h.hostname"
            cursor = connection.cursor()
            cursor.execute(querystring)
            results = cursor.fetchall()
        
        return render_to_response('results.html', {'hosts': results})
    else:
        return render_to_response('search.html',
                                  {'TYPE_CHOICES': Interface.TYPE_CHOICES,
                                   'DNS_CHOICES': Name.DNS_CHOICES,
                                   'yesno': [(1, 'yes'), (0, 'no')]})


def look(request, host_id):
    """Displays general host information"""
    host = Host.objects.get(id=host_id)
    interfaces = []
    for interface in host.interface_set.all():
        interfaces.append([interface, interface.ip_set.all()])
    return render_to_response('host.html',
                              {'host': host,
                               'interfaces': interfaces})
                                   
def dns(request, host_id):
    host = Host.objects.get(id=host_id)
    ips = []
    info = []
    cnames = []
    mxs = []
    for interface in host.interface_set.all():
        ips.extend(interface.ip_set.all())
    for ip in ips:
        info.append([ip, ip.name_set.all()])
        for name in ip.name_set.all():
            cnames.extend(name.cname_set.all())
            mxs.append((name.id, name.mxs.all()))
    return render_to_response('dns.html',
                              {'host': host,
                               'info': info,
                               'cnames': cnames,
                               'mxs': mxs})

def gethostdata(host_id, dnsdata=False):
    """Grabs the necessary data about a host
    Replaces a lot of repeated code"""
    hostdata = {}
    hostdata['ips'] = {}
    hostdata['names'] = {}
    hostdata['cnames'] = {}
    hostdata['mxs'] = {}
    hostdata['host'] = Host.objects.get(id=host_id)
    hostdata['interfaces'] = hostdata['host'].interface_set.all()
    for interface in hostdata['interfaces']:
        hostdata['ips'][interface.id] = interface.ip_set.all()
        if dnsdata:
            for ip in hostdata['ips'][interface.id]:
                hostdata['names'][ip.id] = ip.name_set.all()
                for name in hostdata['names'][ip.id]:
                    hostdata['cnames'][name.id] = name.cname_set.all()
                    hostdata['mxs'][name.id] = name.mxs.all()
    return hostdata

def fill(template, hostdata, dnsdata=False):
    """Fills a generic template
    Replaces a lot of repeated code"""
    if dnsdata:
        template.names = hostdata['names']
        template.cnames = hostdata['cnames']
        template.mxs = hostdata['mxs']
    template.host = hostdata['host']
    template.interfaces = hostdata['interfaces']
    template.ips = hostdata['ips']
    return template

def edit(request, host_id):
    """Edit general host information
    Data is validated before being committed to the database"""
    # fix bug when ip address changes, update the dns info appropriately
    changename = False
    if request.GET.has_key('sub'):
        host = Host.objects.get(id=host_id)
        if request.POST['hostname'] != host.hostname:
            oldhostname = host.hostname.split(".")[0]
            host.hostname = request.POST['hostname']
            host.save()
            changename = True
        interfaces = host.interface_set.all()
        if not validate(request, False, host_id):
            if (request.POST.has_key('outbound_smtp')
                and not host.outbound_smtp or
                not request.POST.has_key('outbound_smtp')
                and host.outbound_smtp):
                host.outbound_smtp = not host.outbound_smtp
            if (request.POST.has_key('dhcp') and not host.dhcp or
                not request.POST.has_key('dhcp') and host.dhcp):
                host.dhcp = not host.dhcp
            # add validation for attribs here
            # likely use a helper fucntion
            for attrib in attribs:
                if request.POST.has_key(attrib):
                    host.__dict__[attrib] = request.POST[attrib].lower()
            if request.POST.has_key('comments'):
                host.comments = request.POST['comments']
            if len(request.POST['expiration_date'].split("-")) == 3:
                (year, month, day) = request.POST['expiration_date'].split("-")
                host.expiration_date = date(int(year), int(month), int(day))
            for inter in interfaces:
                changetype = False
                ips = IP.objects.filter(interface=inter.id)
                if inter.mac_addr != request.POST['mac_addr%d' % inter.id]:
                    inter.mac_addr = request.POST['mac_addr%d' % inter.id]
                if inter.hdwr_type != request.POST['hdwr_type%d' % inter.id]:
                    oldtype = inter.hdwr_type
                    inter.hdwr_type = request.POST['hdwr_type%d' % inter.id]
                    changetype = True
                for ip in ips:
                    names = ip.name_set.all()
                    if not ip.ip_addr == request.POST['ip_addr%d' % ip.id]:
                        oldip = ip.ip_addr
                        oldsubnet = oldip.split(".")[2]
                        ip.ip_addr = request.POST['ip_addr%d' % ip.id]
                        ip.save()
                        for name in names:
                            if name.name.split(".")[0].endswith('-%s' % oldsubnet):
                                name.name = name.name.replace('-%s' % oldsubnet, '-%s' % ip.ip_addr.split(".")[2])
                                name.save()
                    if changetype:
                        for name in names:
                            if name.name.split(".")[0].endswith('-%s' % oldtype):
                                name.name = name.name.replace('-%s' % oldtype, '-%s' % inter.hdwr_type)
                                name.save()
                    if changename:
                        for name in names:
                            if name.name.startswith(oldhostname):
                                name.name = name.name.replace(oldhostname, host.hostname.split(".")[0])
                                name.save()
                if request.POST['%dip_addr' % inter.id]:
                    mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
                    if created:
                        mx.save()
                    new_ip = IP(interface=inter, num=len(ips),
                                ip_addr=request.POST['%dip_addr' % inter.id])
                    new_ip.save()
                    new_name = "-".join([host.hostname.split(".")[0],
                                         new_ip.ip_addr.split(".")[2]])
                    new_name += "." + host.hostname.split(".", 1)[1]
                    name = Name(ip=new_ip, name=new_name,
                                dns_view='global', only=False)
                    name.save()
                    name.mxs.add(mx)
                    new_name = "-".join([host.hostname.split(".")[0],
                                         inter.hdwr_type])
                    new_name += "." + host.hostname.split(".", 1)[1]
                    name = Name(ip=new_ip, name=new_name,
                                dns_view='global', only=False)
                    name.save()
                    name.mxs.add(mx)
                    name = Name(ip=new_ip, name=host.hostname,
                                dns_view='global', only=False)
                    name.save()
                    name.mxs.add(mx)
                inter.save()
            if request.POST['mac_addr_new']:
                new_inter = Interface(host=host,
                                      mac_addr=request.POST['mac_addr_new'],
                                      hdwr_type=request.POST['hdwr_type_new'])
                new_inter.save()
            if request.POST['mac_addr_new'] and request.POST['ip_addr_new']:
                mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
                if created:
                    mx.save()
                new_ip = IP(interface=new_inter, num=0,
                            ip_addr=request.POST['ip_addr_new'])
                new_ip.save()
                new_name = "-".join([host.hostname.split(".")[0],
                                     new_ip.ip_addr.split(".")[2]])
                new_name += "." + host.hostname.split(".", 1)[1]
                name = Name(ip=new_ip, name=new_name,
                            dns_view='global', only=False)
                name.save()
                name.mxs.add(mx)
                new_name = "-".join([host.hostname.split(".")[0],
                                     new_inter.hdwr_type])
                new_name += "." + host.hostname.split(".", 1)[1]
                name = Name(ip=new_ip, name=new_name,
                            dns_view='global', only=False)
                name.save()
                name.mxs.add(mx)
                name = Name(ip=new_ip, name=host.hostname,
                            dns_view='global', only=False)
                name.save()
                name.mxs.add(mx)
            if request.POST['ip_addr_new'] and not request.POST['mac_addr_new']:
                mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
                if created:
                    mx.save()
                new_inter = Interface(host=host, mac_addr="",
                                      hdwr_type=request.POST['hdwr_type_new'])
                new_inter.save()
                new_ip = IP(interface=new_inter, num=0,
                            ip_addr=request.POST['ip_addr_new'])
                new_ip.save()
                new_name = "-".join([host.hostname.split(".")[0],
                                     new_ip.ip_addr.split(".")[2]])
                new_name += "." + host.hostname.split(".", 1)[1]
                name = Name(ip=new_ip, name=new_name,
                            dns_view='global', only=False)
                name.save()
                new_name = "-".join([host.hostname.split(".")[0],
                                     new_inter.hdwr_type])
                new_name += "." + host.hostname.split(".", 1)[1]
                name = Name(ip=new_ip, name=new_name,
                            dns_view='global', only=False)
                name.save()
                name = Name(ip=new_ip, name=host.hostname,
                            dns_view='global', only=False)
                name.save()
            host.save()
            return HttpResponseRedirect('/hostbase/%s/' % host.id)
        else:
            return render_to_response('errors.html',
                                      {'failures': validate(request, False, host_id)})
    else:
        host = Host.objects.get(id=host_id)
        interfaces = []
        for interface in host.interface_set.all():
            interfaces.append([interface, interface.ip_set.all()])
        return render_to_response('edit.html',
                                  {'host': host,
                                   'interfaces': interfaces,
                                   'TYPE_CHOICES': Interface.TYPE_CHOICES})

def confirm(request, item, item_id, host_id=None, name_id=None, zone_id=None):
    """Asks if the user is sure he/she wants to remove an item"""
    if request.GET.has_key('sub'):
        if item == 'interface':
            for ip in Interface.objects.get(id=item_id).ip_set.all():
                for name in ip.name_set.all():
                    name.cname_set.all().delete()
                ip.name_set.all().delete()
            Interface.objects.get(id=item_id).ip_set.all().delete()
            Interface.objects.get(id=item_id).delete()
        elif item=='ip':
            for name in IP.objects.get(id=item_id).name_set.all():
                name.cname_set.all().delete()
            IP.objects.get(id=item_id).name_set.all().delete()
            IP.objects.get(id=item_id).delete()
        elif item=='cname':
            CName.objects.get(id=item_id).delete()
        elif item=='mx':
            mx = MX.objects.get(id=item_id)
            Name.objects.get(id=name_id).mxs.remove(mx)
        elif item=='name':
            Name.objects.get(id=item_id).cname_set.all().delete()
            Name.objects.get(id=item_id).delete()
        elif item=='nameserver':
            nameserver = Nameserver.objects.get(id=item_id)
            Zone.objects.get(id=zone_id).nameservers.remove(nameserver)
        elif item=='zonemx':
            mx = MX.objects.get(id=item_id)
            Zone.objects.get(id=zone_id).mxs.remove(mx)
        elif item=='address':
            address = ZoneAddress.objects.get(id=item_id)
            Zone.objects.get(id=zone_id).addresses.remove(address)
        if item == 'cname' or item == 'mx' or item == 'name':
            return HttpResponseRedirect('/hostbase/%s/dns/edit' % host_id)
        elif item == 'nameserver' or item == 'zonemx' or item == 'address':
            return HttpResponseRedirect('/hostbase/zones/%s/edit' % zone_id)
        else:
            return HttpResponseRedirect('/hostbase/%s/edit' % host_id)
    else:
        interface = None
        ips = []
        names = []
        cnames = []
        mxs = []
        zonemx = None
        nameserver = None
        address = None
        if item == 'interface':
            interface = Interface.objects.get(id=item_id)
            ips = interface.ip_set.all()
            for ip in ips:
                for name in ip.name_set.all():
                    names.append((ip.id, name))
                    for cname in name.cname_set.all():
                        cnames.append((name.id, cname))
                    for mx in name.mxs.all():
                        mxs.append((name.id, mx))
        elif item=='ip':
            ips = [IP.objects.get(id=item_id)]
            for name in ips[0].name_set.all():
                names.append((ips[0].id, name))
                for cname in name.cname_set.all():
                    cnames.append((name.id, cname))
                for mx in name.mxs.all():
                    mxs.append((name.id, mx))
        elif item=='name':
            names = [Name.objects.get(id=item_id)]
            for cname in names[0].cname_set.all():
                cnames.append((names[0].id, cname))
            for mx in names[0].mxs.all():
                mxs.append((names[0].id, mx))
        elif item=='cname':
            cnames = [CName.objects.get(id=item_id)]
        elif item=='mx':
            mxs = [MX.objects.get(id=item_id)]
        elif item=='zonemx':
            zonemx = MX.objects.get(id=item_id)
        elif item=='nameserver':
            nameserver = Nameserver.objects.get(id=item_id)
        elif item=='address':
            address = ZoneAddress.objects.get(id=item_id)
        return render_to_response('confirm.html',
                                  {'interface': interface,
                                   'ips': ips,
                                   'names': names,
                                   'cnames': cnames,
                                   'id': item_id,
                                   'type': item,
                                   'host_id': host_id,
                                   'mxs': mxs,
                                   'zonemx': zonemx,
                                   'nameserver': nameserver,
                                   'address': address,
                                   'zone_id': zone_id})

def dnsedit(request, host_id):
    """Edits specific DNS information
    Data is validated before committed to the database"""
    if request.GET.has_key('sub'):
        hostdata = gethostdata(host_id, True)
        for ip in hostdata['names']:
            ipaddr = IP.objects.get(id=ip)
            ipaddrstr = ipaddr.__str__()
            for name in hostdata['cnames']:
                for cname in hostdata['cnames'][name]:
                    cname.cname = request.POST['cname%d' % cname.id]
                    cname.save()
            for name in hostdata['mxs']:
                for mx in hostdata['mxs'][name]:
                    mx.priority = request.POST['priority%d' % mx.id]
                    mx.mx = request.POST['mx%d' % mx.id]
                    mx.save()
            for name in hostdata['names'][ip]:
                name.name = request.POST['name%d' % name.id]
                if request.POST['%dcname' % name.id]:
                    cname = CName(name=name,
                                  cname=request.POST['%dcname' % name.id])
                    cname.save()
                if (request.POST['%dpriority' % name.id] and
                    request.POST['%dmx' % name.id]):
                    mx, created = MX.objects.get_or_create(priority=request.POST['%dpriority' % name.id],
                            mx=request.POST['%dmx' % name.id])
                    if created:
                        mx.save()
                    name.mxs.add(mx)
                name.save()
            if request.POST['%sname' % ipaddrstr]:
                name = Name(ip=ipaddr,
                            dns_view=request.POST['%sdns_view' % ipaddrstr],
                            name=request.POST['%sname' % ipaddrstr], only=False)
                name.save()
                if request.POST['%scname' % ipaddrstr]:
                    cname = CName(name=name,
                                  cname=request.POST['%scname' % ipaddrstr])
                    cname.save()
                if (request.POST['%smx' % ipaddrstr] and
                    request.POST['%spriority' % ipaddrstr]):
                    mx, created = MX.objects.get_or_create(priority=request.POST['%spriority' % ipaddrstr],
                            mx=request.POST['%smx' % ipaddrstr])
                    if created:
                        mx.save()
                    name.mxs.add(mx)                
        return HttpResponseRedirect('/hostbase/%s/dns' % host_id)
    else:
        host = Host.objects.get(id=host_id)
        ips = []
        info = []
        cnames = []
        mxs = []
        interfaces = host.interface_set.all()
        for interface in host.interface_set.all():
            ips.extend(interface.ip_set.all())
        for ip in ips:
            info.append([ip, ip.name_set.all()])
            for name in ip.name_set.all():
                cnames.extend(name.cname_set.all())
                mxs.append((name.id, name.mxs.all()))
        return render_to_response('dnsedit.html',
                                  {'host': host,
                                   'info': info,
                                   'cnames': cnames,
                                   'mxs': mxs,
                                   'request': request,
                                   'interfaces': interfaces,
                                   'DNS_CHOICES': Name.DNS_CHOICES})
    
def new(request):
    """Function for creating a new host in hostbase
    Data is validated before committed to the database"""
    if request.GET.has_key('sub'):
        try:
            Host.objects.get(hostname=request.POST['hostname'].lower())
            return render_to_response('errors.html',
                                      {'failures': ['%s already exists in hostbase' % request.POST['hostname']]})
        except:
            pass
        if not validate(request, True):
            host = Host()
            # this is the stuff that validate() should take care of
            # examine the check boxes for any changes
            host.outbound_smtp = request.POST.has_key('outbound_smtp')
            host.dhcp = request.POST.has_key('dhcp')
            for attrib in attribs:
                if request.POST.has_key(attrib):
                    host.__dict__[attrib] = request.POST[attrib].lower()
            if request.POST.has_key('comments'):
                host.comments = request.POST['comments']
            if request.POST.has_key('expiration_date'):
                host.__dict__['expiration_date'] = date(2000, 1, 1)
            host.status = 'active'
            host.save()
        else:
            return render_to_response('errors.html',
                                      {'failures': validate(request, True)})
        if request.POST['mac_addr_new']:
            new_inter = Interface(host=host,
                                  mac_addr=request.POST['mac_addr_new'],
                                  hdwr_type=request.POST['hdwr_type_new'])
            new_inter.save()
        if request.POST['mac_addr_new'] and request.POST['ip_addr_new']:
            new_ip = IP(interface=new_inter,
                        num=0, ip_addr=request.POST['ip_addr_new'])
            new_ip.save()
            mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
            if created:
                mx.save()
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_ip.ip_addr.split(".")[2]])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name, dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_inter.hdwr_type])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            name = Name(ip=new_ip, name=host.hostname,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
        if request.POST['ip_addr_new'] and not request.POST['mac_addr_new']:
            new_inter = Interface(host=host,
                                  mac_addr="",
                                  hdwr_type=request.POST['hdwr_type_new1'])
            new_inter.save()
            new_ip = IP(interface=new_inter, num=0,
                        ip_addr=request.POST['ip_addr_new1'])
            new_ip.save()
            mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
            if created:
                mx.save()
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_ip.ip_addr.split(".")[2]])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_inter.hdwr_type])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            name = Name(ip=new_ip, name=host.hostname,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
        if request.POST['mac_addr_new2']:
            new_inter = Interface(host=host,
                                  mac_addr=request.POST['mac_addr_new2'],
                                  hdwr_type=request.POST['mac_addr_new2'])
            new_inter.save()
        if request.POST['mac_addr_new2'] and request.POST['ip_addr_new2']:
            new_ip = IP(interface=new_inter, num=0,
                        ip_addr=request.POST['ip_addr_new2'])
            new_ip.save()
            mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
            if created:
                mx.save()
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_ip.ip_addr.split(".")[2]])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_inter.hdwr_type])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            name = Name(ip=new_ip, name=host.hostname,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
        if request.POST['ip_addr_new2'] and not request.POST['mac_addr_new2']:
            new_inter = Interface(host=host,
                                  mac_addr="",
                                  hdwr_type=request.POST['hdwr_type_new2'])
            new_inter.save()
            new_ip = IP(interface=new_inter, num=0,
                        ip_addr=request.POST['ip_addr_new2'])
            new_ip.save()
            mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
            if created:
                mx.save()
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_ip.ip_addr.split(".")[2]])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            new_name = "-".join([host.hostname.split(".")[0],
                                 new_inter.hdwr_type])
            new_name += "." + host.hostname.split(".", 1)[1]
            name = Name(ip=new_ip, name=new_name,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
            name = Name(ip=new_ip, name=host.hostname,
                        dns_view='global', only=False)
            name.save()
            name.mxs.add(mx)
        host.save()
        return HttpResponseRedirect('/hostbase/%s/' % host.id)
    else:
        return render_to_response('new.html',
                                  {'TYPE_CHOICES': Interface.TYPE_CHOICES,
                                   'NETGROUP_CHOICES': Host.NETGROUP_CHOICES,
                                   'CLASS_CHOICES': Host.CLASS_CHOICES,
                                   'SUPPORT_CHOICES': Host.SUPPORT_CHOICES,
                                   'WHATAMI_CHOICES': Host.WHATAMI_CHOICES})                                   
    
def remove(request, host_id):
    host = Host.objects.get(id=host_id)
    if request.has_key('sub'):
        for interface in host.interface_set.all():
            for ip in interface.ip_set.all():
                for name in ip.name_set.all():
                    name.cname_set.all().delete()
                ip.name_set.all().delete()
            interface.ip_set.all().delete()
            interface.delete()
        host.delete()
        return HttpResponseRedirect('/hostbase/')
    else:
        """Displays general host information"""
        interfaces = []
        for interface in host.interface_set.all():
            interfaces.append([interface, interface.ip_set.all()])
        return render_to_response('remove.html',
                                  {'host': host,
                                   'interfaces': interfaces})

def validate(request, new=False, host_id=None):
    """Function for checking form data"""
    failures = []
    if (request.POST['expiration_date']
        and regex.date.match(request.POST['expiration_date'])):
        try:
            (year, month, day) = request.POST['expiration_date'].split("-")
            date(int(year), int(month), int(day))
        except (ValueError):
            failures.append('expiration_date')
    elif request.POST['expiration_date']:
        failures.append('expiration_date')

    if not (request.POST['hostname']
            and regex.host.match(request.POST['hostname'])):
        failures.append('hostname')

    if not regex.printq.match(request.POST['printq']) and request.POST['printq']:
        failures.append('printq')

    if not regex.user.match(request.POST['primary_user']):
        failures.append('primary_user')

    if (not regex.user.match(request.POST['administrator'])
        and request.POST['administrator']):
        failures.append('administrator')

    if not (request.POST['location']
            and regex.location.match(request.POST['location'])):
        failures.append('location')

    if new:
        if (not regex.macaddr.match(request.POST['mac_addr_new'])
            and request.POST['mac_addr_new']):
            failures.append('mac_addr (#1)')
        if ((request.POST['mac_addr_new'] or request.POST['ip_addr_new']) and
            not request.has_key('hdwr_type_new')):
            failures.append('hdwr_type (#1)')
        if ((request.POST['mac_addr_new2'] or request.POST['ip_addr_new2']) and
            not request.has_key('hdwr_type_new2')):
            failures.append('hdwr_type (#2)')

        if (not regex.macaddr.match(request.POST['mac_addr_new2'])
            and request.POST['mac_addr_new2']):
            failures.append('mac_addr (#2)')

        if (not regex.ipaddr.match(request.POST['ip_addr_new'])
            and request.POST['ip_addr_new']):
            failures.append('ip_addr (#1)')
        if (not regex. ipaddr.match(request.POST['ip_addr_new2'])
            and request.POST['ip_addr_new2']):
            failures.append('ip_addr (#2)')

        [failures.append('ip_addr (#1)') for number in
         request.POST['ip_addr_new'].split(".")
         if number.isdigit() and int(number) > 255
         and 'ip_addr (#1)' not in failures]
        [failures.append('ip_addr (#2)') for number in
         request.POST['ip_addr_new2'].split(".")
         if number.isdigit() and int(number) > 255
         and 'ip_addr (#2)' not in failures]

    elif host_id:
        interfaces = Interface.objects.filter(host=host_id)
        for interface in interfaces:
            if (not regex.macaddr.match(request.POST['mac_addr%d' % interface.id])
                and request.POST['mac_addr%d' % interface.id]):
                failures.append('mac_addr (%s)' % request.POST['mac_addr%d' % interface.id])
            for ip in interface.ip_set.all():
                if not regex.ipaddr.match(request.POST['ip_addr%d' % ip.id]):
                    failures.append('ip_addr (%s)' % request.POST['ip_addr%d' % ip.id])
                [failures.append('ip_addr (%s)' % request.POST['ip_addr%d' % ip.id])
                 for number in request.POST['ip_addr%d' % ip.id].split(".")
                 if (number.isdigit() and int(number) > 255 and
                     'ip_addr (%s)' % request.POST['ip_addr%d' % ip.id] not in failures)]
            if (request.POST['%dip_addr' % interface.id]
                and not regex.ipaddr.match(request.POST['%dip_addr' % interface.id])):
                failures.append('ip_addr (%s)' % request.POST['%dip_addr' % interface.id])
        if (request.POST['mac_addr_new']
            and not regex.macaddr.match(request.POST['mac_addr_new'])):
            failures.append('mac_addr (%s)' % request.POST['mac_addr_new'])
        if (request.POST['ip_addr_new']
            and not regex.ipaddr.match(request.POST['ip_addr_new'])):
            failures.append('ip_addr (%s)' % request.POST['ip_addr_new'])

    if not failures:
        return 0
    return failures

def zones(request):
    zones = Zone.objects.all()
    return render_to_response('zones.html',
                              {'zones': zones})

def zoneview(request, zone_id):
    zone = Zone.objects.get(id=zone_id)
    return render_to_response('zoneview.html',
                              {'zone': zone,
                               'nameservers': zone.nameservers.all(),
                               'mxs': zone.mxs.all(),
                               'addresses': zone.addresses.all()
                               })

def zoneedit(request, zone_id):
    if request.GET.has_key('sub'):
        zone = Zone.objects.get(id=zone_id)
        for attrib in zoneattribs:
            if request.POST.has_key(attrib):
                zone.__dict__[attrib] = request.POST[attrib]
        count = 0
        for nameserver in zone.nameservers.all():
            ns, created = Nameserver.objects.get_or_create(name=request.POST['nameserver%i' % count])
            if created or not (nameserver == ns):
                ns.save()
                zone.nameservers.add(ns)
                zone.nameservers.remove(nameserver)
            count += 1
        count = 0
        for mx in zone.mxs.all():
            mrecord, created = MX.objects.get_or_create(priority=request.POST['priority%i' % count],
                                                        mx=request.POST['mx%i' % count])
            if created or not (mx == mrecord):
                mrecord.save()
                zone.mxs.add(mrecord)
                zone.mxs.remove(mx)
            count += 1
        count = 0
        for address in zone.addresses.all():
            arecord, created = ZoneAddress.objects.get_or_create(ip_addr=request.POST['address%i' % count])
            if created or not (arecord == address):
                arecord.save()
                zone.addresses.add(arecord)
                zone.addresses.remove(address)
            count += 1
        zone.save()
        if request.POST['new_nameserver']:
            nameserver, created = Nameserver.objects.get_or_create(name=request.POST['new_nameserver'])
            if created:
                nameserver.save()
            zone.nameservers.add(nameserver)
        if request.POST['new_mx'] and request.POST['new_priority']:
            mx, created = MX.objects.get_or_create(priority=request.POST['new_priority'],
                                                   mx=request.POST['new_mx'])
            if created:
                mx.save()
            zone.mxs.add(mx)
        if request.POST['new_address'] and not request.POST['new_address'] == 'none':
            address, created = ZoneAddress.objects.get_or_create(ip_addr=request.POST['new_address'])
            if created:
                address.save()
            zone.addresses.add(address)
        return HttpResponseRedirect('/hostbase/zones/%s/' % zone.id)
    else:
        zone = Zone.objects.get(id=zone_id)
        return render_to_response('zoneedit.html',
                                  {'zone': zone,
                                   'nameservers': zone.nameservers.all(),
                                   'mxs': zone.mxs.all(),
                                   'addresses': zone.addresses.all()
                                   })

def zonenew(request):
    if request.GET.has_key('sub'):
        try:
            Zone.objects.get(zone=request.POST['zone'])
            return render_to_response('errors.html',
                                      {'failures': ['%s already exists in database' % request.POST['zone']]})
        except:
            zone = Zone(zone=request.POST['zone'])
        for attrib in zoneattribs:
            if request.POST.has_key(attrib):
                zone.__dict__[attrib] = request.POST[attrib]
        zone.serial = 1
        zone.save()
        for num in range(0,4):
            if request.POST['nameserver%i' % num]:
                ns, created = Nameserver.objects.get_or_create(name=request.POST['nameserver%i' % num])
                if created:
                    ns.save()
                zone.nameservers.add(ns)
        for num in range(0,2):
            if request.POST['priority%i' % num] and request.POST['mx%i' % num]:
                mrecord, created = MX.objects.get_or_create(priority=request.POST['priority%i' % num],
                                                            mx=request.POST['mx%i' % num])
                if created:
                    mrecord.save()
                zone.mxs.add(mrecord)
        for num in range(0,2):
            if request.POST['address%i' % num]:
                arecord, created = ZoneAddress.objects.get_or_create(ip_addr=request.POST['address%i' % num])
                if created:
                    arecord.save()
                zone.addresses.add(arecord)
        return HttpResponseRedirect('/hostbase/zones/%s/' % zone.id)
    else:
        return render_to_response('zonenew.html',
                                  {'nameservers': range(0,4),
                                  'mxs': range(0,2),
                                  'addresses': range(0,2)
                                   })

if settings.CFG_TYPE == 'environ':
    #login required stuff
    search = login_required(search)
    look = login_required(look)
    dns = login_required(dns)
    gethostdata = login_required(gethostdata)
    fill = login_required(fill)
    edit = login_required(edit)
    confirm = login_required(confirm)
    dnsedit = login_required(dnsedit)
    new = login_required(new)
    remove = login_required(remove)
    validate = login_required(validate)
    zones = login_required(zones)
    zoneview = login_required(zoneview)
    zoneedit = login_required(zoneedit)
    zonenew = login_required(zonenew)
    
else:
    pass

