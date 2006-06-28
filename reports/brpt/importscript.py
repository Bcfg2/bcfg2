#! /usr/bin/env python
'''Imports statistics.xml and clients.xml files in to database backend for statistics'''
__revision__ = '$Revision$'

import os, sys
#i can clean all of this up to be like two lines...
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
#got everything ready; lets do stuff

from brpt.reports.models import Client, Interaction, Bad, Modified, Extra, Performance
from lxml.etree import XML, XMLSyntaxError
from sys import argv
from getopt import getopt, GetoptError
from datetime import datetime
from time import strptime

if __name__ == '__main__':
#need clients.xml
#need statistics.xml

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

    
    #for client in clientsdata.findall('Client'):
    for node in statsdata.findall('Node'):
        #if client_rec.name == node.get('name'):
        (client_rec, cr_created) = Client.objects.get_or_create(name=node.get('name'), defaults={'name': node.get('name'), 'creation': datetime.now()})
#        if cr_created:
#            client_rec.save()
        for statistics in node.findall('Statistics'):
            t = strptime(statistics.get('time'))
            (interaction_rec, ir_created) = Interaction.objects.get_or_create(client=client_rec.id,timestamp=datetime(t[0],t[1],t[2],t[3],t[4],t[5]),
                                                                              defaults={'client':client_rec,
                                                                                        'timestamp':datetime(t[0],t[1],t[2],t[3],t[4],t[5]),
                                                                                        'state':statistics.get('state', default="unknown"),
                                                                                        'repo_revision':statistics.get('revision', default="unknown"),
                                                                                        'client_version':statistics.get('client_version'),
                                                                                        'goodcount':statistics.get('good', default="unknown"),
                                                                                        'totalcount':statistics.get('total', default="unknown")})
            for bad in statistics.findall('Bad'):
                for ele in bad.getchildren():
                    (ele_rec, er_created) = Bad.objects.get_or_create(name=ele.get('name'), kind=ele.tag,
                                                                      defaults={'name':ele.get('name'),
                                                                                'kind':ele.tag,
                                                                                'problemcode':'',
                                                                                'reason':'Unknown'})
                        
                    if not ele_rec in interaction_rec.bad_items.all():
                        interaction_rec.bad_items.add(ele_rec)

            for modified in statistics.findall('Modified'):
                for ele in modified.getchildren():
                    (ele_rec, er_created) = Modified.objects.get_or_create(name=ele.get('name'), kind=ele.tag,
                                                                           defaults={'name':ele.get('name'),
                                                                                     'kind':ele.tag,
                                                                                     'problemcode':'',
                                                                                     'reason':'Unknown'})
                    if not ele_rec in interaction_rec.modified_items.all():
                        interaction_rec.modified_items.add(ele_rec)

            for extra in statistics.findall('Extra'):
                for ele in extra.getchildren():
                    (ele_rec, er_created) = Extra.objects.get_or_create(name=ele.get('name'), kind=ele.tag,
                                                                        defaults={'name':ele.get('name'),
                                                                                  'kind':ele.tag,
                                                                                  'problemcode':'',
                                                                                  'reason':'Unknown'})
                        
                    if not ele_rec in interaction_rec.extra_items.all():
                        interaction_rec.extra_items.add(ele_rec)
                                
                        #try to find extra element with given name and type and problemcode and reason
                        #if ones doesn't exist create it
                        #try to get associated bad element
                        #if one is not associated, associate it


            for times in statistics.findall('OpStamps'):
                for tags in times.items():
                    (time_rec, tr_created) = Performance.objects.get_or_create(metric=tags[0], value=tags[1],
                                                                               defaults={'metric':tags[0],
                                                                                         'value':tags[1]})
                    if not ele_rec in interaction_rec.extra_items.all():
                        interaction_rec.performance_items.add(time_rec)
                    


#print Client.objects.all().order_by('-name')[0].name

