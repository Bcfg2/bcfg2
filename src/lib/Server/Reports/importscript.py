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

from Bcfg2.Server.Reports.reports.models import Client, Interaction, Bad, Modified, Extra, Performance, Reason
from lxml.etree import XML, XMLSyntaxError
from sys import argv
from getopt import getopt, GetoptError
from datetime import datetime
from time import strptime, sleep
from django.db import connection, backend
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

    try:
        opts, args = getopt(argv[1:], "hvudc:s:", ["help", "verbose", "updates" ,"debug", "clients=", "stats="])
    except GetoptError, mesg:
        # print help information and exit:
        print "%s\nUsage:\nimportscript.py [-h] [-v] [-u] [-d] [-C bcfg2 config file] [-c clients-file] [-s statistics-file]" % (mesg) 
        raise SystemExit, 2
    opts.append(("1","1"))#this requires the loop run at least once
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
        if o in ("-C"):
            cpath = a
        else:
            cpath = "/etc/bcfg2.conf"

        cf = ConfigParser.ConfigParser()
        cf.read([cpath])
		
        if o in ("-v", "--verbose"):
            verbose = True
        if o in ("-u", "--updates"):
            somewhatverbose = True
        if o in ("-d", "--debug"):
            veryverbose = True
        if o in ("-c", "--clients"):
            clientspath = a
        else:
            try:
                clientspath = "%s/Metadata/clients.xml"%cf.get('server', 'repository')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                print "Could not read bcfg2.conf; exiting"
                raise SystemExit, 1

        if o in ("-s", "--stats"):
            statpath = a
        else:
            try:
                statpath = "%s/etc/statistics.xml"%cf.get('server', 'repository')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                print "Could not read bcfg2.conf; exiting"
                raise SystemExit, 1

    '''Reads Data & Config files'''
    try:
        statsdata = XML(open(statpath).read())
    except (IOError, XMLSyntaxError):
        print("StatReports: Failed to parse %s"%(statpath))
        raise SystemExit, 1
    try:
        clientsdata = XML(open(clientspath).read())
    except (IOError, XMLSyntaxError):
        print("StatReports: Failed to parse %s"%(clientspath))
        raise SystemExit, 1

    cursor = connection.cursor()
    clients = {}
    cursor.execute("SELECT name, id from reports_client;")
    [clients.__setitem__(a,b) for a,b in cursor.fetchall()]
    
    for node in statsdata.findall('Node'):
        name = node.get('name')
        if not clients.has_key(name):
            cursor.execute("INSERT INTO reports_client VALUES (NULL, %s, %s, NULL, NULL)", [datetime.now(),name])
            clients[name] = cursor.lastrowid
            if verbose:
                print("Client %s added to db"%name)
        else:
            if verbose:
                print("Client %s already exists in db"%name)

    pingability = {}
    [pingability.__setitem__(n.get('name'),n.get('pingable',default='N')) for n in clientsdata.findall('Client')]
    

    cursor.execute("SELECT id, metric, value from reports_performance")
    performance_hash = {}
    [performance_hash.__setitem__((n[1],n[2]),n[0]) for n in cursor.fetchall()]

    cursor.execute("SELECT x.client_id, reports_ping.status from (SELECT client_id, MAX(endtime) from reports_ping GROUP BY client_id) x, reports_ping WHERE x.client_id = reports_ping.client_id")
    ping_hash = {}
    [ping_hash.__setitem__(n[0],n[1]) for n in cursor.fetchall()]

    
    for r in statsdata.findall('.//Bad/*')+statsdata.findall('.//Extra/*')+statsdata.findall('.//Modified/*'):
        kargs = build_reason_kwargs(r)
        rlist = \
              Reason.objects.filter(**kargs)
        if rlist:
            current_reason_id = rlist[0].id
            if verbose:
                print("Reason already exists. It's ID is: %s"%current_reason_id)
        else:
            reason = Reason(**kargs)
            reason.save()
            current_reason_id = reason.id
            if verbose:
                print("Reason inserted with id %s"%current_reason_id)

    if (somewhatverbose or verbose):
        print "----------------REASONS SYNCED---------------------"
    
    for node in statsdata.findall('Node'):
        name = node.get('name')
        c_inst = Client.objects.filter(id=clients[name])[0]
        try:
            pingability[name]
        except KeyError:
            pingability[name] = 'N'
        for statistics in node.findall('Statistics'):
            t = strptime(statistics.get('time'))
            timestamp = datetime(t[0],t[1],t[2],t[3],t[4],t[5])#Maybe replace with django.core.db typecasts typecast_timestamp()? import from django.backends util
            ilist = Interaction.objects.filter(client=c_inst,
                                               timestamp=timestamp)
            if ilist:
                current_interaction_id = ilist[0].id
                if verbose:
                    print("Interaction for %s at %s with id %s already exists"%(clients[name],
                        datetime(t[0],t[1],t[2],t[3],t[4],t[5]),current_interaction_id))
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


            pattern = [('Bad/*', Bad), ('Extra/*', Extra),
                       ('Modified/*', Modified)]
            for (xpath, obj) in pattern:
                for x in statistics.findall(xpath):
                    kargs = build_reason_kwargs(x)
                    rr = Reason.objects.filter(**kargs)[0]
                    links = obj.objects.filter(name=x.get('name'),
                                               kind=x.tag,
                                               reason=rr.id)
                    if links:
                        item_id = links[0].id
                        if verbose:
                            print "%s item exists, has reason id %s and ID %s"%(xpath, rr.id, item_id)
                    else:
                        newitem = obj(name=x.get('name'),
                                      kind=x.tag,
                                      reason=rr.id)
                        newitem.save()
                        item_id = newitem.id
                        if verbose:
                            print "Bad item INSERTED having reason id %s and ID %s"%(rr.id, item_id)
                    try:
                        cursor.execute("INSERT INTO "+tablename+"_interactions VALUES (NULL, %s, %s);",
                                       [item_id, current_interaction_id])
                    except:
                        pass                    

            for times in statistics.findall('OpStamps'):
                for tags in times.items():
                    if not performance_hash.has_key((tags[0],float(tags[1]))):
                        cursor.execute("INSERT INTO reports_performance VALUES (NULL, %s, %s)",[tags[0],tags[1]])
                        performance_hash[(tags[0],tags[1])] = cursor.lastrowid
                    else:
                        item_id = performance_hash[(tags[0],float(tags[1]))]
                        #already exists
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
        if clients.has_key(key):
            if ping_hash.has_key(clients[key]):
                if ping_hash[clients[key]] == pingability[key]:
                    cursor.execute("UPDATE reports_ping SET endtime = %s where reports_ping.client_id = %s",
                                   [datetime.now(),clients[key]])
                else:
                    ping_hash[clients[key]] = pingability[key]
                    cursor.execute("INSERT INTO reports_ping VALUES (NULL, %s, %s, %s, %s)",
                                   [clients[key], datetime.now(), datetime.now(), pingability[key]])
            else:
                ping_hash[clients[key]] = pingability[key]
                cursor.execute("INSERT INTO reports_ping VALUES (NULL, %s, %s, %s, %s)",
                               [clients[key], datetime.now(), datetime.now(), pingability[key]])

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
