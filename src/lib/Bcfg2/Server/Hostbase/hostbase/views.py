"""Views.py
Contains all the views associated with the hostbase app
Also has does form validation
"""
from django.http import HttpResponse, HttpResponseRedirect

from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.template import RequestContext
from Bcfg2.Server.Hostbase.hostbase.models import *
from datetime import date
from django.db import connection
from django.shortcuts import render_to_response
from django import forms
from Bcfg2.Server.Hostbase import settings, regex
import re, copy

attribs = ['hostname', 'whatami', 'netgroup', 'security_class', 'support',
           'csi', 'printq', 'primary_user', 'administrator', 'location',
           'status', 'comments']

zoneattribs = ['zone', 'admin', 'primary_master', 'expire', 'retry',
               'refresh', 'ttl', 'aux']

dispatch = {'mac_addr':'i.mac_addr LIKE \'%%%%%s%%%%\'',
            'ip_addr':'p.ip_addr LIKE \'%%%%%s%%%%\'',
            'name':'n.name LIKE \'%%%%%s%%%%\'',
##             'hostname':'n.name LIKE \'%%%%%s%%%%\'',
##             'cname':'n.name LIKE \'%%%%%s%%%%\'',
            'mx':'m.mx LIKE \'%%%%%s%%%%\'',
            'dns_view':'n.dns_view = \'%s\'',
            'hdwr_type':'i.hdwr_type = \'%s\'',
            'dhcp':'i.dhcp = \'%s\''}

def search(request):
    """Search for hosts in the database
    If more than one field is entered, logical AND is used
    """
    if 'sub' in request.GET:
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
            if request.POST[field] and field == 'hostname':
                if _and:
                    querystring += ' AND '
                querystring +=  'n.name LIKE \'%%%%%s%%%%\' or c.cname LIKE \'%%%%%s%%%%\'' % (request.POST[field], request.POST[field])
                _and = True
            elif request.POST[field] and field in dispatch:
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

        return render_to_response('results.html',
                                  {'hosts': results,
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))
    else:
        return render_to_response('search.html',
                                  {'TYPE_CHOICES': Interface.TYPE_CHOICES,
                                   'DNS_CHOICES': Name.DNS_CHOICES,
                                   'yesno': [(1, 'yes'), (0, 'no')],
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))


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
    """edit general host information"""
    manipulator = Host.ChangeManipulator(host_id)
    changename = False
    if request.method == 'POST':
        host = Host.objects.get(id=host_id)
        before = host.__dict__.copy()
        if request.POST['hostname'] != host.hostname:
            oldhostname = host.hostname.split(".")[0]
            changename = True
        interfaces = host.interface_set.all()
        old_interfaces = [interface.__dict__.copy() for interface in interfaces]

        new_data = request.POST.copy()

        errors = manipulator.get_validation_errors(new_data)
        if not errors:

            # somehow keep track of multiple interface change manipulators
            # as well as multiple ip chnage manipulators??? (add manipulators???)
            # change to many-to-many??????

            # dynamically look up mx records?
            text = ''

            for attrib in attribs:
                if host.__dict__[attrib] != request.POST[attrib]:
                    text = do_log(text, attrib, host.__dict__[attrib], request.POST[attrib])
                    host.__dict__[attrib] = request.POST[attrib]

            if 'expiration_date' in request.POST:
                ymd = request.POST['expiration_date'].split("-")
                if date(int(ymd[0]), int(ymd[1]), int(ymd[2])) != host.__dict__['expiration_date']:
                    text = do_log(text, 'expiration_date', host.__dict__['expiration_date'],
                                  request.POST['expiration_date'])
                    host.__dict__['expiration_date'] = date(int(ymd[0]), int(ymd[1]), int(ymd[2]))

            for inter in interfaces:
                changetype = False
                ips = IP.objects.filter(interface=inter.id)
                if inter.mac_addr != request.POST['mac_addr%d' % inter.id]:
                    text = do_log(text, 'mac_addr', inter.mac_addr, request.POST['mac_addr%d' % inter.id])
                    inter.mac_addr = request.POST['mac_addr%d' % inter.id].lower().replace('-',':')
                if inter.hdwr_type != request.POST['hdwr_type%d' % inter.id]:
                    oldtype = inter.hdwr_type
                    text = do_log(text, 'hdwr_type', oldtype, request.POST['hdwr_type%d' % inter.id])
                    inter.hdwr_type = request.POST['hdwr_type%d' % inter.id]
                    changetype = True
                if (('dhcp%d' % inter.id) in request.POST and not inter.dhcp or
                    not ('dhcp%d' % inter.id) in request.POST and inter.dhcp):
                    text = do_log(text, 'dhcp', inter.dhcp, int(not inter.dhcp))
                    inter.dhcp = not inter.dhcp
                for ip in ips:
                    names = ip.name_set.all()
                    if not ip.ip_addr == request.POST['ip_addr%d' % ip.id]:
                        oldip = ip.ip_addr
                        oldsubnet = oldip.split(".")[2]
                        ip.ip_addr = request.POST['ip_addr%d' % ip.id]
                        ip.save()
                        text = do_log(text, 'ip_addr', oldip, ip.ip_addr)
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
                    new_ip = IP(interface=inter, ip_addr=request.POST['%dip_addr' % inter.id])
                    new_ip.save()
                    text = do_log(text, '*new*', 'ip_addr', new_ip.ip_addr)
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
                                      mac_addr=request.POST['mac_addr_new'].lower().replace('-',':'),
                                      hdwr_type=request.POST['hdwr_type_new'],
                                      dhcp=request.POST['dhcp_new'])
                text = do_log(text, '*new*', 'mac_addr', new_inter.mac_addr)
                new_inter.save()
            if request.POST['mac_addr_new'] and request.POST['ip_addr_new']:
                mx, created = MX.objects.get_or_create(priority=settings.PRIORITY, mx=settings.DEFAULT_MX)
                if created:
                    mx.save()
                new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new'])
                new_ip.save()
                text = do_log(text, '*new*', 'ip_addr', new_ip.ip_addr)
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
                                      hdwr_type=request.POST['hdwr_type_new'],
                                      dhcp=False)
                new_inter.save()
                new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new'])
                new_ip.save()
                text = do_log(text, '*new*', 'ip_addr', new_ip.ip_addr)
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
            if text:
                log = Log(hostname=host.hostname, log=text)
                log.save()
            host.save()
            return HttpResponseRedirect('/hostbase/%s/' % host.id)
        else:
            return render_to_response('errors.html',
                                      {'failures': errors,
                                       'logged_in': request.session.get('_auth_user_id', False)},
                                       context_instance = RequestContext(request))
    else:
        host = Host.objects.get(id=host_id)
        interfaces = []
        for interface in host.interface_set.all():
            interfaces.append([interface, interface.ip_set.all()])
        return render_to_response('edit.html',
                                  {'host': host,
                                   'interfaces': interfaces,
                                   'TYPE_CHOICES': Interface.TYPE_CHOICES,
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))

def confirm(request, item, item_id, host_id=None, name_id=None, zone_id=None):
    """Asks if the user is sure he/she wants to remove an item"""
    if 'sub' in request.GET:
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
                                   'zone_id': zone_id,
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))

def dnsedit(request, host_id):
    """Edits specific DNS information
    Data is validated before committed to the database"""
    text = ''
    if 'sub' in request.GET:
        hostdata = gethostdata(host_id, True)
        for ip in hostdata['names']:
            ipaddr = IP.objects.get(id=ip)
            ipaddrstr = ipaddr.__str__()
            for name in hostdata['cnames']:
                for cname in hostdata['cnames'][name]:
                    if regex.host.match(request.POST['cname%d' % cname.id]):
                        text = do_log(text, 'cname', cname.cname, request.POST['cname%d' % cname.id])
                        cname.cname = request.POST['cname%d' % cname.id]
                        cname.save()
            for name in hostdata['mxs']:
                for mx in hostdata['mxs'][name]:
                    if (mx.priority != request.POST['priority%d' % mx.id] and mx.mx != request.POST['mx%d' % mx.id]):
                        text = do_log(text, 'mx', ' '.join([str(mx.priority), str(mx.mx)]),
                                      ' '.join([request.POST['priority%d' % mx.id], request.POST['mx%d' % mx.id]]))
                        nameobject = Name.objects.get(id=name)
                        nameobject.mxs.remove(mx)
                        newmx, created = MX.objects.get_or_create(priority=request.POST['priority%d' % mx.id], mx=request.POST['mx%d' % mx.id])
                        if created:
                            newmx.save()
                        nameobject.mxs.add(newmx)
                        nameobject.save()
            for name in hostdata['names'][ip]:
                name.name = request.POST['name%d' % name.id]
                name.dns_view = request.POST['dns_view%d' % name.id]
                if (request.POST['%dcname' % name.id] and
                regex.host.match(request.POST['%dcname' % name.id])):
                    cname = CName(name=name,
                                  cname=request.POST['%dcname' % name.id])
                    text = do_log(text, '*new*', 'cname', cname.cname)
                    cname.save()
                if (request.POST['%dpriority' % name.id] and
                    request.POST['%dmx' % name.id]):
                    mx, created = MX.objects.get_or_create(priority=request.POST['%dpriority' % name.id],
                            mx=request.POST['%dmx' % name.id])
                    if created:
                        mx.save()
                        text = do_log(text, '*new*', 'mx',
                                      ' '.join([request.POST['%dpriority' % name.id],
                                                request.POST['%dmx' % name.id]]))
                    name.mxs.add(mx)
                name.save()
            if request.POST['%sname' % ipaddrstr]:
                name = Name(ip=ipaddr,
                            dns_view=request.POST['%sdns_view' % ipaddrstr],
                            name=request.POST['%sname' % ipaddrstr], only=False)
                text = do_log(text, '*new*', 'name', name.name)
                name.save()
                if (request.POST['%scname' % ipaddrstr] and
                regex.host.match(request.POST['%scname' % ipaddrstr])):
                    cname = CName(name=name,
                                  cname=request.POST['%scname' % ipaddrstr])
                    text = do_log(text, '*new*', 'cname', cname.cname)
                    cname.save()
                if (request.POST['%smx' % ipaddrstr] and
                    request.POST['%spriority' % ipaddrstr]):
                    mx, created = MX.objects.get_or_create(priority=request.POST['%spriority' % ipaddrstr],
                            mx=request.POST['%smx' % ipaddrstr])
                    if created:
                        mx.save()
                    text = do_log(text, '*new*', 'mx',
                                  ' '.join([request.POST['%spriority' % ipaddrstr], request.POST['%smx' % ipaddrstr]]))
                    name.mxs.add(mx)
        if text:
            log = Log(hostname=hostdata['host'].hostname, log=text)
            log.save()
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
                                   'DNS_CHOICES': Name.DNS_CHOICES,
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))

def new(request):
    """Function for creating a new host in hostbase
    Data is validated before committed to the database"""
    if 'sub' in request.GET:
        try:
            Host.objects.get(hostname=request.POST['hostname'].lower())
            return render_to_response('errors.html',
                                      {'failures': ['%s already exists in hostbase' % request.POST['hostname']],
                                       'logged_in': request.session.get('_auth_user_id', False)},
                                       context_instance = RequestContext(request))
        except:
            pass
        if not validate(request, True):
            if not request.POST['ip_addr_new'] and not request.POST['ip_addr_new2']:
                return render_to_response('errors.html',
                                          {'failures': ['ip_addr: You must enter an ip address'],
                                          'logged_in': request.session.get('_auth_user_id', False)},
                                          context_instance = RequestContext(request))
            host = Host()
            # this is the stuff that validate() should take care of
            # examine the check boxes for any changes
            host.outbound_smtp = 'outbound_smtp' in request.POST
            for attrib in attribs:
                if attrib in request.POST:
                    host.__dict__[attrib] = request.POST[attrib].lower()
            if 'comments' in request.POST:
                host.comments = request.POST['comments']
            if 'expiration_date' in request.POST:
#                ymd = request.POST['expiration_date'].split("-")
#                host.__dict__['expiration_date'] = date(int(ymd[0]), int(ymd[1]), int(ymd[2]))
                host.__dict__['expiration_date'] = date(2000, 1, 1)
            host.status = 'active'
            host.save()
        else:
            return render_to_response('errors.html',
                                      {'failures': validate(request, True),
                                       'logged_in': request.session.get('_auth_user_id', False)},
                                       context_instance = RequestContext(request))

        if request.POST['mac_addr_new']:
            new_inter = Interface(host=host,
                                  mac_addr = request.POST['mac_addr_new'].lower().replace('-',':'),
                                  hdwr_type = request.POST['hdwr_type_new'],
                                  dhcp = 'dhcp_new' in request.POST)
            new_inter.save()
        if request.POST['mac_addr_new'] and request.POST['ip_addr_new']:
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new'])
# Change all this things. Use a "post_save" signal handler for model Host to create all sociate models
# and use a generi view.
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
                                  hdwr_type=request.POST['hdwr_type_new'],
                                  dhcp=False)
            new_inter.save()
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new'])
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
                                  mac_addr = request.POST['mac_addr_new2'].lower().replace('-',':'),
                                  hdwr_type = request.POST['hdwr_type_new2'],
                                  dhcp = 'dhcp_new2' in request.POST)
            new_inter.save()
        if request.POST['mac_addr_new2'] and request.POST['ip_addr_new2']:
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new2'])
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
                                  hdwr_type=request.POST['hdwr_type_new2'],
                                  dhcp=False)
            new_inter.save()
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new2'])
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
                                   'WHATAMI_CHOICES': Host.WHATAMI_CHOICES,
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))

def copy(request, host_id):
    """Function for creating a new host in hostbase
    Data is validated before committed to the database"""
    if 'sub' in request.GET:
        try:
            Host.objects.get(hostname=request.POST['hostname'].lower())
            return render_to_response('errors.html',
                                      {'failures': ['%s already exists in hostbase' % request.POST['hostname']],
                                       'logged_in': request.session.get('_auth_user_id', False)},
                                       context_instance = RequestContext(request))
        except:
            pass
        if not validate(request, True):
            if not request.POST['ip_addr_new'] and not request.POST['ip_addr_new2']:
                return render_to_response('errors.html',
                                          {'failures': ['ip_addr: You must enter an ip address'],
                                          'logged_in': request.session.get('_auth_user_id', False)},
                                          context_instance = RequestContext(request))
            host = Host()
            # this is the stuff that validate() should take care of
            # examine the check boxes for any changes
            host.outbound_smtp = 'outbound_smtp' in request.POST
            for attrib in attribs:
                if attrib in request.POST:
                    host.__dict__[attrib] = request.POST[attrib].lower()
            if 'comments' in request.POST:
                host.comments = request.POST['comments']
            if 'expiration_date' in request.POST:
#                ymd = request.POST['expiration_date'].split("-")
#                host.__dict__['expiration_date'] = date(int(ymd[0]), int(ymd[1]), int(ymd[2]))
                host.__dict__['expiration_date'] = date(2000, 1, 1)
            host.status = 'active'
            host.save()
        else:
            return render_to_response('errors.html',
                                      {'failures': validate(request, True),
                                       'logged_in': request.session.get('_auth_user_id', False)},
                                       context_instance = RequestContext(request))

        if request.POST['mac_addr_new']:
            new_inter = Interface(host=host,
                                  mac_addr = request.POST['mac_addr_new'].lower().replace('-',':'),
                                  hdwr_type = request.POST['hdwr_type_new'],
                                  dhcp = 'dhcp_new' in request.POST)
            new_inter.save()
        if request.POST['mac_addr_new'] and request.POST['ip_addr_new']:
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new'])
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
                                  hdwr_type=request.POST['hdwr_type_new'],
                                  dhcp=False)
            new_inter.save()
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new'])
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
                                  mac_addr = request.POST['mac_addr_new2'].lower().replace('-',':'),
                                  hdwr_type = request.POST['hdwr_type_new2'],
                                  dhcp = 'dhcp_new2' in request.POST)
            new_inter.save()
        if request.POST['mac_addr_new2'] and request.POST['ip_addr_new2']:
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new2'])
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
                                  hdwr_type=request.POST['hdwr_type_new2'],
                                  dhcp=False)
            new_inter.save()
            new_ip = IP(interface=new_inter, ip_addr=request.POST['ip_addr_new2'])
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
        host = Host.objects.get(id=host_id)
        return render_to_response('copy.html',
                                  {'host': host,
                                   'TYPE_CHOICES': Interface.TYPE_CHOICES,
                                   'NETGROUP_CHOICES': Host.NETGROUP_CHOICES,
                                   'CLASS_CHOICES': Host.CLASS_CHOICES,
                                   'SUPPORT_CHOICES': Host.SUPPORT_CHOICES,
                                   'WHATAMI_CHOICES': Host.WHATAMI_CHOICES,
                                   'logged_in': request.session.get('_auth_user_id', False)},
                                   context_instance = RequestContext(request))

# FIXME: delete all this things in a signal handler "pre_delete"
#def remove(request, host_id):
#    host = Host.objects.get(id=host_id)
#    if 'sub' in request:
#        for interface in host.interface_set.all():
#            for ip in interface.ip_set.all():
#                for name in ip.name_set.all():
#                    name.cname_set.all().delete()
#                ip.name_set.all().delete()
#            interface.ip_set.all().delete()
#            interface.delete()
#        host.delete()

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

##     if not regex.printq.match(request.POST['printq']) and request.POST['printq']:
##         failures.append('printq')

##     if not regex.user.match(request.POST['primary_user']):
##         failures.append('primary_user')

##     if (not regex.user.match(request.POST['administrator'])
##         and request.POST['administrator']):
##         failures.append('administrator')

##     if not (request.POST['location']
##             and regex.location.match(request.POST['location'])):
##         failures.append('location')

    if new:
        if (not regex.macaddr.match(request.POST['mac_addr_new'])
            and request.POST['mac_addr_new']):
            failures.append('mac_addr (#1)')
        if ((request.POST['mac_addr_new'] or request.POST['ip_addr_new']) and
            not 'hdwr_type_new' in request.REQUEST):
            failures.append('hdwr_type (#1)')
        if ((request.POST['mac_addr_new2'] or request.POST['ip_addr_new2']) and
            not 'hdwr_type_new2' in request.REQUEST):
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

def do_log(text, attribute, previous, new):
    if previous != new:
        text += "%-20s%-20s -> %s\n" % (attribute, previous, new)
    return text

## login required stuff
## uncomment the views below that you would like to restrict access to

## uncomment the lines below this point to restrict access to pages that modify the database
## anonymous users can still view data in Hostbase

edit = login_required(edit)
confirm = login_required(confirm)
dnsedit = login_required(dnsedit)
new = login_required(new)
copy = login_required(copy)
#remove = login_required(remove)
#zoneedit = login_required(zoneedit)
#zonenew = login_required(zonenew)

## uncomment the lines below this point to restrict access to all of hostbase

## search = login_required(search)
## look = login_required(look)
## dns = login_required(dns)
## zones = login_required(zones)
## zoneview = login_required(zoneview)

