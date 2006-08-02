#! /usr/bin/env python
'''Imports statistics.xml and clients.xml files in to database backend for new statistics engine'''
__revision__ = '$Revision$'

import os, sys
try:    # Add this project to sys.path so that it's importable
    import settings # Assumed to be in the same directory.
except ImportError:
    sys.stderr.write("Failed to locate settings.py")
    sys.exit(1)

project_directory = os.path.dirname(settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()
# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name

from brpt.reports.models import Client, Interaction, Bad, Modified, Extra, Performance, Reason
from lxml.etree import XML, XMLSyntaxError
from sys import argv
from getopt import getopt, GetoptError
from datetime import datetime
from time import strptime, sleep

if __name__ == '__main__':
    somewhatverbose = False
    verbose = False
    veryverbose = False
    try:
        opts, args = getopt(argv[1:], "hvudc:s:", ["help", "verbose", "updates" ,"debug", "clients=", "stats="])
    except GetoptError, mesg:
        # print help information and exit:
        print "%s\nUsage:\nimportscript.py [-h] [-v] [-u] [-d] -c <clients-file> -s <statistics-file>" % (mesg) 
        raise SystemExit, 2
    for o, a in opts:
        if o in ("-h", "--help"):
            print "Usage:\nimportscript.py [-h] [-v] -c <clients-file> -s <statistics-file> \n"
            print "h : help; this message"
            print "v : verbose; print messages on record insertion/skip"
            print "u : updates; print status messages as items inserted semi-verbose"
            print "d : debug; print most SQL used to manipulate database"
            print "c : clients.xml file"
            print "s : statistics.xml file"
            raise SystemExit
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

    from django.db import connection, backend
    cursor = connection.cursor()

    clients = {}
    cursor.execute("SELECT name, id from reports_client;")
    [clients.__setitem__(a,b) for a,b in cursor.fetchall()]
    
    for node in statsdata.findall('Node'):
        name = node.get('name')
        if not clients.has_key(name):
            cursor.execute("INSERT INTO reports_client VALUES (NULL, %s, %s, NULL)", [datetime.now(),name])
            clients[name] = cursor.lastrowid
            if verbose:
                print("Client %s added to db"%name)
        else:
            if verbose:
                print("Client %s already exists in db"%name)


    cursor.execute("SELECT client_id, timestamp, id from reports_interaction")
    interactions_hash = {}
    [interactions_hash.__setitem__(str(x[0])+"-"+x[1].isoformat(),x[2]) for x in cursor.fetchall()]#possibly change str to tuple
    pingability = {}
    [pingability.__setitem__(n.get('name'),n.get('pingable',default='N')) for n in clientsdata.findall('Client')]
    

    cursor.execute("SELECT id, owner, current_owner, %s, current_group, perms, current_perms, status, current_status, %s, current_to, version, current_version, current_exists, current_diff from reports_reason"%(backend.quote_name("group"),backend.quote_name("to")))
    reasons_hash = {}
    [reasons_hash.__setitem__(tuple(n[1:]),n[0]) for n in cursor.fetchall()]

    cursor.execute("SELECT id, name, kind, reason_id from reports_bad")
    bad_hash = {}
    [bad_hash.__setitem__((n[1],n[2]),(n[0],n[3])) for n in cursor.fetchall()]

    cursor.execute("SELECT id, name, kind, reason_id from reports_extra")
    extra_hash = {}
    [extra_hash.__setitem__((n[1],n[2]),(n[0],n[3])) for n in cursor.fetchall()]

    cursor.execute("SELECT id, name, kind, reason_id from reports_modified")
    modified_hash = {}
    [modified_hash.__setitem__((n[1],n[2]),(n[0],n[3])) for n in cursor.fetchall()]

    cursor.execute("SELECT id, metric, value from reports_performance")
    performance_hash = {}
    [performance_hash.__setitem__((n[1],n[2]),n[0]) for n in cursor.fetchall()]
    
    for r in statsdata.findall('.//Bad/*')+statsdata.findall('.//Extra/*')+statsdata.findall('.//Modified/*'):
        arguments = [r.get('owner', default=""), r.get('current_owner', default=""),
                     r.get('group', default=""), r.get('current_group', default=""),
                     r.get('perms', default=""), r.get('current_perms', default=""),
                     r.get('status', default=""), r.get('current_status', default=""),
                     r.get('to', default=""), r.get('current_to', default=""),
                     r.get('version', default=""), r.get('current_version', default=""),
                     (r.get('current_exists', default="True").capitalize()=="True"),
                     r.get('current_diff', default="")]
        if reasons_hash.has_key(tuple(arguments)):
            current_reason_id = reasons_hash[tuple(arguments)]
            if verbose:
                print("Reason already exists..... It's ID is: %s"%current_reason_id)
        else:
            cursor.execute("INSERT INTO reports_reason VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                           arguments)
            current_reason_id = cursor.lastrowid
            reasons_hash[tuple(arguments)] = current_reason_id
            if verbose:
                print("Reason inserted with id %s"%current_reason_id)
    if (somewhatverbose or verbose):
        print "----------------REASONS SYNCED---------------------"
    
    for node in statsdata.findall('Node'):
        name = node.get('name')
        try:
            pingability[name]
        except KeyError:
            pingability[name] = 'N'
        for statistics in node.findall('Statistics'):
            t = strptime(statistics.get('time'))
            timestamp = datetime(t[0],t[1],t[2],t[3],t[4],t[5])
            if interactions_hash.has_key(str(clients[name]) +"-"+ timestamp.isoformat()):
                current_interaction_id = interactions_hash[str(clients[name])+"-"+timestamp.isoformat()]
                if verbose:
                    print("Interaction for %s at %s with id %s already exists"%(clients[name],
                        datetime(t[0],t[1],t[2],t[3],t[4],t[5]),current_interaction_id))
            else:
                cursor.execute("INSERT INTO reports_interaction VALUES (NULL, %s, %s, %s, %s, %s, %s, %s);",
                               [clients[name], timestamp,
                                statistics.get('state', default="unknown"), statistics.get('revision',default="unknown"),
                                statistics.get('client_version',default="unknown"),
                                statistics.get('good',default="0"), statistics.get('total',default="0")])
                current_interaction_id = cursor.lastrowid
                interactions_hash[str(clients[name])+"-"+timestamp.isoformat()] = current_interaction_id
                if verbose:
                    print("Interaction for %s at %s with id %s INSERTED in to db"%(clients[name],
                        timestamp, current_interaction_id))

            #get current ping info
            #figure out which ones changed
            #update ones that didn't change, just update endtime
            #if it doesn't exist, create a new one with starttime and endtime==now
            #if it does exist, insert new with start time equal to the previous endtime, endtime==now
            
            #if (somewhatverbose or verbose):
            #    print "---------------PINGDATA SYNCED---------------------"

            for (xpath, hashname, tablename) in [('Bad/*', bad_hash, 'reports_bad'),
                                                 ('Extra/*', extra_hash, 'reports_extra'),
                                                 ('Modified/*', modified_hash, 'reports_modified')]:
                for x in statistics.findall(xpath):
                    if not hashname.has_key((x.get('name'), x.tag)):
                        arguments = [x.get('owner', default=""), x.get('current_owner', default=""),
                                     x.get('group', default=""), x.get('current_group', default=""),
                                     x.get('perms', default=""), x.get('current_perms', default=""),
                                     x.get('status', default=""), x.get('current_status', default=""),
                                     x.get('to', default=""), x.get('current_to', default=""),
                                     x.get('version', default=""), x.get('current_version', default=""),
                                     (x.get('current_exists', default="True").capitalize()=="True"),
                                     x.get('current_diff', default="")]
                        cursor.execute("INSERT INTO "+tablename+" VALUES (NULL, %s, %s, %s, %s);",
                                       [x.get('name'),
                                        x.tag,
                                        (x.get('critical', default="False").capitalize()=="True"),
                                        reasons_hash[tuple(arguments)]])
                        item_id = cursor.lastrowid
                        hashname[(x.get('name'), x.tag)] = (item_id, current_interaction_id)
                    if verbose:
                        print "Bad item INSERTED having reason id %s and ID %s"%(hashname[(x.get('name'),x.tag)][1],
                                                                                 hashname[(x.get('name'),x.tag)][0])                
                    else:
                        item_id = hashname[(x.get('name'), x.tag)][0]
                        if verbose:
                            print "Bad item exists, has reason id %s and ID %s"%(hashname[(x.get('name'),x.tag)][1],
                                                                                          hashname[(x.get('name'),x.tag)][0])
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
