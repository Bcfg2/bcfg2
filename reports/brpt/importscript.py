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
from time import strptime

if __name__ == '__main__':

    try:
        opts, args = getopt(argv[1:], "hc:s:", ["help", "clients=", "stats="])
    except GetoptError, mesg:
        # print help information and exit:
        print "%s\nUsage:\nStatReports.py [-h] -c <clients-file> -s <statistics-file>" % (mesg) 
        raise SystemExit, 2
    for o, a in opts:
        if o in ("-h", "--help"):
            print "Usage:\nStatReports.py [-h] -c <clients-file> -s <statistics-file>"
            raise SystemExit
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

    for node in statsdata.findall('Node'):
        (client_rec, cr_created) = Client.objects.get_or_create(name=node.get('name'),
                                        defaults={'name': node.get('name'), 'creation': datetime.now()})

        for statistics in node.findall('Statistics'):
            t = strptime(statistics.get('time'))
            (interaction_rec, ir_created) = Interaction.objects.get_or_create(client=client_rec.id,
                                                timestamp=datetime(t[0],t[1],t[2],t[3],t[4],t[5]),
                                                defaults={'client':client_rec,
                                                          'timestamp':datetime(t[0],t[1],t[2],t[3],t[4],t[5]),
                                                          'state':statistics.get('state', default="unknown"),
                                                          'repo_revision':statistics.get('revision', default="unknown"),
                                                          'client_version':statistics.get('client_version'),
                                                          'goodcount':statistics.get('good', default="unknown"),
                                                          'totalcount':statistics.get('total', default="unknown")})
            for bad in statistics.findall('Bad'):
                for ele in bad.getchildren():
                    (reason_rec, rr_created) = Reason.objects.get_or_create(owner=ele.get('owner',default=''),
                                                        current_owner=ele.get('current_owner',default=''),
                                                        group=ele.get('group',default=''),
                                                        current_group=ele.get('current_group',default=''),
                                                        perms=ele.get('perms',default=''),
                                                        current_perms=ele.get('current_perms',default=''),
                                                        status=ele.get('status',default=''),
                                                        current_status=ele.get('current_status',default=''),
                                                        to=ele.get('to',default=''),
                                                        current_to=ele.get('current_to',default=''),
                                                        version=ele.get('version',default=''),
                                                        current_version=ele.get('current_version',default=''),
                                                        current_exists=ele.get('current_exists',default='True'),
                                                        current_diff=ele.get('current_diff',default=''),
                                                        defaults={'owner':ele.get('owner',default=''),
                                                                  'current_owner':ele.get('current_owner',default=''),
                                                                  'group':ele.get('group',default=''),
                                                                  'current_group':ele.get('current_group',default=''),
                                                                  'perms':ele.get('perms',default=''),
                                                                  'current_perms':ele.get('current_perms',default=''),
                                                                  'status':ele.get('status',default=''),
                                                                  'current_status':ele.get('current_status',default=''),
                                                                  'to':ele.get('to',default=''),
                                                                  'current_to':ele.get('current_to',default=''),
                                                                  'version':ele.get('version',default=''),
                                                                  'current_version':ele.get('current_version',default=''),
                                                                  'current_exists':ele.get('current_exists',default='True'),
                                                                  'current_diff':ele.get('current_diff',default='')})
                        

                    (ele_rec, er_created) = Bad.objects.get_or_create(name=ele.get('name'), kind=ele.tag,
                                                defaults={'name':ele.get('name'),
                                                          'kind':ele.tag,
                                                          'reason':reason_rec})

                    if not ele_rec in interaction_rec.bad_items.all():
                        interaction_rec.bad_items.add(ele_rec)

            for modified in statistics.findall('Modified'):
                for ele in modified.getchildren():
                    (reason_rec, rr_created) = Reason.objects.get_or_create(owner=ele.get('owner',default=''),
                                                        current_owner=ele.get('current_owner',default=''),
                                                        group=ele.get('group',default=''),
                                                        current_group=ele.get('current_group',default=''),
                                                        perms=ele.get('perms',default=''),
                                                        current_perms=ele.get('current_perms',default=''),
                                                        status=ele.get('status',default=''),
                                                        current_status=ele.get('current_status',default=''),
                                                        to=ele.get('to',default=''),
                                                        current_to=ele.get('current_to',default=''),
                                                        version=ele.get('version',default=''),
                                                        current_version=ele.get('current_version',default=''),
                                                        current_exists=ele.get('current_exists',default='True'),
                                                        current_diff=ele.get('current_diff',default=''),
                                                        defaults={'owner':ele.get('owner',default=''),
                                                                  'current_owner':ele.get('current_owner',default=''),
                                                                  'group':ele.get('group',default=''),
                                                                  'current_group':ele.get('current_group',default=''),
                                                                  'perms':ele.get('perms',default=''),
                                                                  'current_perms':ele.get('current_perms',default=''),
                                                                  'status':ele.get('status',default=''),
                                                                  'current_status':ele.get('current_status',default=''),
                                                                  'to':ele.get('to',default=''),
                                                                  'current_to':ele.get('current_to',default=''),
                                                                  'version':ele.get('version',default=''),
                                                                  'current_version':ele.get('current_version',default=''),
                                                                  'current_exists':ele.get('current_exists',default='True'),
                                                                  'current_diff':ele.get('current_diff',default='')})
                        

                    (ele_rec, er_created) = Modified.objects.get_or_create(name=ele.get('name'), kind=ele.tag,
                                                defaults={'name':ele.get('name'),
                                                          'kind':ele.tag,
                                                          'reason':reason_rec})
                    if not ele_rec in interaction_rec.modified_items.all():
                        interaction_rec.modified_items.add(ele_rec)

            for extra in statistics.findall('Extra'):
                for ele in extra.getchildren():
                    (reason_rec, rr_created) = Reason.objects.get_or_create(owner=ele.get('owner',default=''),
                                                        current_owner=ele.get('current_owner',default=''),
                                                        group=ele.get('group',default=''),
                                                        current_group=ele.get('current_group',default=''),
                                                        perms=ele.get('perms',default=''),
                                                        current_perms=ele.get('current_perms',default=''),
                                                        status=ele.get('status',default=''),
                                                        current_status=ele.get('current_status',default=''),
                                                        to=ele.get('to',default=''),
                                                        current_to=ele.get('current_to',default=''),
                                                        version=ele.get('version',default=''),
                                                        current_version=ele.get('current_version',default=''),
                                                        current_exists=ele.get('current_exists',default='True'),
                                                        current_diff=ele.get('current_diff',default=''),
                                                        defaults={'owner':ele.get('owner',default=''),
                                                                  'current_owner':ele.get('current_owner',default=''),
                                                                  'group':ele.get('group',default=''),
                                                                  'current_group':ele.get('current_group',default=''),
                                                                  'perms':ele.get('perms',default=''),
                                                                  'current_perms':ele.get('current_perms',default=''),
                                                                  'status':ele.get('status',default=''),
                                                                  'current_status':ele.get('current_status',default=''),
                                                                  'to':ele.get('to',default=''),
                                                                  'current_to':ele.get('current_to',default=''),
                                                                  'version':ele.get('version',default=''),
                                                                  'current_version':ele.get('current_version',default=''),
                                                                  'current_exists':ele.get('current_exists',default='True'),
                                                                  'current_diff':ele.get('current_diff',default='')})
                        

                    (ele_rec, er_created) = Extra.objects.get_or_create(name=ele.get('name'), kind=ele.tag,
                                                defaults={'name':ele.get('name'),
                                                          'kind':ele.tag,
                                                          'reason':reason_rec})
                        
                    if not ele_rec in interaction_rec.extra_items.all():
                        interaction_rec.extra_items.add(ele_rec)

            for times in statistics.findall('OpStamps'):
                for tags in times.items():
                    (time_rec, tr_created) = Performance.objects.get_or_create(metric=tags[0], value=tags[1],
                                                    defaults={'metric':tags[0],
                                                              'value':tags[1]})
                    if not ele_rec in interaction_rec.extra_items.all():
                        interaction_rec.performance_items.add(time_rec)
