#! /usr/bin/env python
'''Imports statistics.xml and clients.xml files in to database backend for new statistics engine'''
__revision__ = '$Revision$'

import os, sys, binascii
try:
    import settings
except ImportError:
    try:
        import Bcfg2.Server.Reports.settings
    except ImportError:
        sys.stderr.write("Failed to locate settings.py. Is Bcfg2.Server.Reports python module installed?")
        sys.exit(1)

project_directory = os.path.dirname(settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()
# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name

from Bcfg2.Server.Reports.reports.models import Client, Interaction, Bad, Modified, Extra, Performance, Reason, Ping
from lxml.etree import XML, XMLSyntaxError
from sys import argv
from getopt import getopt, GetoptError
from datetime import datetime
from time import strptime
from django.db import connection
import ConfigParser

def build_reason_kwargs(r_ent):
    if r_ent.get('current_bdiff', False):
        rc_diff = binascii.a2b_base64(r_ent.get('current_bdiff'))
    else:
        rc_diff = r_ent.get('current_diff', '')
    return dict(owner=r_ent.get('owner', default=""),
                current_owner=r_ent.get('current_owner', default=""),
                group=r_ent.get('group', default=""),
                current_group=r_ent.get('current_group', default=""),
                perms=r_ent.get('perms', default=""),
                current_perms=r_ent.get('current_perms', default=""),
                status=r_ent.get('status', default=""),
                current_status=r_ent.get('current_status', default=""),
                to=r_ent.get('to', default=""),
                current_to=r_ent.get('current_to', default=""),
                version=r_ent.get('version', default=""),
                current_version=r_ent.get('current_version', default=""),
                current_exists=r_ent.get('current_exists', default="True").capitalize()=="True",
                current_diff=rc_diff)

if __name__ == '__main__':
    somewhatverbose = False
    verbose = False
    veryverbose = False
    cpath = "/etc/bcfg2.conf"
    clientpath = False
    statpath = False
    
    try:
        opts, args = getopt(argv[1:], "hvudc:s:", ["help", "verbose", "updates" ,
                                                   "debug", "clients=", "stats=",
                                                   "config="])
    except GetoptError, mesg:
        # print help information and exit:
        print "%s\nUsage:\nimportscript.py [-h] [-v] [-u] [-d] [-C bcfg2 config file] [-c clients-file] [-s statistics-file]" % (mesg) 
        raise SystemExit, 2

    for o, a in opts:
        if o in ("-h", "--help"):
            print "Usage:\nimportscript.py [-h] [-v] -c <clients-file> -s <statistics-file> \n"
            print "h : help; this message"
            print "v : verbose; print messages on record insertion/skip"
            print "u : updates; print status messages as items inserted semi-verbose"
            print "d : debug; print most SQL used to manipulate database"
            print "C : path to bcfg2.conf config file."
            print "c : clients.xml file"
            print "s : statistics.xml file"
            raise SystemExit
        if o in ["-C", "--config"]:
            cpath = a

        if o in ("-v", "--verbose"):
            verbose = True
        if o in ("-u", "--updates"):
            somewhatverbose = True
        if o in ("-d", "--debug"):
            veryverbose = True
        if o in ("-c", "--clients"):
            clientspath = a

        if o in ("-s", "--stats"):
            statpath = a

    cf = ConfigParser.ConfigParser()
    cf.read([cpath])

    if not statpath:
        try:
            statpath = "%s/etc/statistics.xml" % cf.get('server', 'repository')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            print "Could not read bcfg2.conf; exiting"
            raise SystemExit, 1
    try:
        statsdata = XML(open(statpath).read())
    except (IOError, XMLSyntaxError):
        print("StatReports: Failed to parse %s"%(statpath))
        raise SystemExit, 1

    if not clientpath:
        try:
            clientspath = "%s/Metadata/clients.xml" % \
                          cf.get('server', 'repository')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            print "Could not read bcfg2.conf; exiting"
            raise SystemExit, 1
    try:
        clientsdata = XML(open(clientspath).read())
    except (IOError, XMLSyntaxError):
        print("StatReports: Failed to parse %s"%(clientspath))
        raise SystemExit, 1

    cursor = connection.cursor()
    clients = {}
    cursor.execute("SELECT name, id from reports_client;")
    [clients.__setitem__(a, b) for a, b in cursor.fetchall()]
    
    for node in statsdata.findall('Node'):
        name = node.get('name')
        if not clients.has_key(name):
            cursor.execute(\
                "INSERT INTO reports_client VALUES (NULL, %s, %s, NULL, NULL)",
                [datetime.now(), name])
            clients[name] = cursor.lastrowid
            if verbose:
                print("Client %s added to db" % name)
        else:
            if verbose:
                print("Client %s already exists in db" % name)

    pingability = {}
    [pingability.__setitem__(n.get('name'), n.get('pingable', default='N')) \
     for n in clientsdata.findall('Client')]

    for node in statsdata.findall('Node'):
        name = node.get('name')
        c_inst = Client.objects.filter(id=clients[name])[0]
        try:
            pingability[name]
        except KeyError:
            pingability[name] = 'N'
        for statistics in node.findall('Statistics'):
            t = strptime(statistics.get('time'))
            # Maybe replace with django.core.db typecasts typecast_timestamp()?
            # import from django.backends util
            timestamp = datetime(t[0], t[1], t[2], t[3], t[4], t[5])
            ilist = Interaction.objects.filter(client=c_inst,
                                               timestamp=timestamp)
            if ilist:
                current_interaction_id = ilist[0].id
                if verbose:
                    print("Interaction for %s at %s with id %s already exists"%(clients[name],
                        datetime(t[0],t[1],t[2],t[3],t[4],t[5]),current_interaction_id))
                continue
            else:
                newint = Interaction(client=c_inst,
                                     timestamp=timestamp,
                                     state=statistics.get('state', default="unknown"),
                                     repo_revision=statistics.get('revision',default="unknown"),
                                     client_version=statistics.get('client_version',default="unknown"),
                                     goodcount=statistics.get('good',default="0"),
                                     totalcount=statistics.get('total',default="0"))
                newint.save()
                current_interaction_id = newint.id
                if verbose:
                    print("Interaction for %s at %s with id %s INSERTED in to db"%(clients[name],
                        timestamp, current_interaction_id))


            pattern = [('Bad/*', Bad, 'reports_bad'),
                       ('Extra/*', Extra, 'reports_extra'),
                       ('Modified/*', Modified, 'reports_modified')]
            for (xpath, obj, tablename) in pattern:
                for x in statistics.findall(xpath):
                    kargs = build_reason_kwargs(x)
                    rls = Reason.objects.filter(**kargs)
                    if rls:
                        rr = rls[0]
                        if verbose:
                            print "Reason exists: %s"% (rr.id)
                    else:
                        rr = Reason(**kargs)
                        rr.save()
                        if verbose:
                            print "Created reason: %s" % rr.id
                    links = obj.objects.filter(name=x.get('name'),
                                               kind=x.tag,
                                               reason=rr)
                    if links:
                        item_id = links[0].id
                        if verbose:
                            print "%s item exists, has reason id %s and ID %s" % (xpath, rr.id, item_id)
                    else:
                        newitem = obj(name=x.get('name'),
                                      kind=x.tag,
                                      reason=rr)
                        newitem.save()
                        item_id = newitem.id
                        if verbose:
                            print "Bad item INSERTED having reason id %s and ID %s" % (rr.id, item_id)
                    try:
                        cursor.execute("INSERT INTO "+tablename+"_interactions VALUES (NULL, %s, %s);",
                                       [item_id, current_interaction_id])
                    except:
                        pass                    

            for times in statistics.findall('OpStamps'):
                for metric, value in times.items():
                    mmatch = Performance.objects.filter(metric=metric, value=value)
                    if mmatch:
                        item_id = mmatch[0].id
                    else:
                        mperf = Performance(metric=metric, value=value)
                        mperf.save()
                        item_id = mperf.id
                    try:
                        cursor.execute("INSERT INTO reports_performance_interaction VALUES (NULL, %s, %s);",
                                       [item_id, current_interaction_id])
                    except:
                        pass

    if (somewhatverbose or verbose):
        print("----------------INTERACTIONS SYNCED----------------")
    cursor.execute("select reports_interaction.id, x.client_id from (select client_id, MAX(timestamp) as timer from reports_interaction Group BY client_id) x, reports_interaction where reports_interaction.client_id = x.client_id AND reports_interaction.timestamp = x.timer")
    for row in cursor.fetchall():
        cursor.execute("UPDATE reports_client SET current_interaction_id = %s where reports_client.id = %s",
                       [row[0],row[1]])
    if (somewhatverbose or verbose):
        print("------------LATEST INTERACTION SET----------------")

    for key in pingability.keys():
        if key not in clients:
            #print "Ping Save Problem with client %s" % name
            continue
        cmatch = Client.objects.filter(id=clients[key])[0]
        pmatch = Ping.objects.filter(client=cmatch).order_by('-endtime')
        if pmatch:
            if pmatch[0].status == pingability[key]:
                pmatch[0].endtime = datetime.now()
                pmatch[0].save()
            else:
                newp = Ping(client=cmatch, status=pingability[key],
                            starttime=datetime.now(),
                            endtime=datetime.now())
                newp.save()
        else:
            newp = Ping(client=cmatch, status=pingability[key],
                        starttime=datetime.now(), endtime=datetime.now())
            newp.save()

    if (somewhatverbose or verbose):
        print "---------------PINGDATA SYNCED---------------------"

    connection._commit()
    #Clients are consistent
    if veryverbose:
        for q in connection.queries:
            if not (q['sql'].startswith('INSERT INTO reports_bad_interactions')|
                    q['sql'].startswith('INSERT INTO reports_extra_interactions')|
                    q['sql'].startswith('INSERT INTO reports_performance_interaction')|
                    q['sql'].startswith('INSERT INTO reports_modified_interactions')|
                    q['sql'].startswith('UPDATE reports_client SET current_interaction_id ')):
                print q

    raise SystemExit, 0
