#! /usr/bin/env python
"""
Imports statistics.xml and clients.xml files in to database backend for
new statistics engine
"""
__revision__ = '$Revision$'

import binascii
import os
import sys
try:
    import Bcfg2.Server.Reports.settings
except Exception:
    e = sys.exc_info()[1]
    sys.stderr.write("Failed to load configuration settings. %s\n" % e)
    sys.exit(1)

project_directory = os.path.dirname(Bcfg2.Server.Reports.settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()
# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name

from Bcfg2.Server.Reports.reports.models import *
from lxml.etree import XML, XMLSyntaxError
from getopt import getopt, GetoptError
from datetime import datetime
from time import strptime
from django.db import connection
from Bcfg2.Server.Reports.updatefix import update_database
import logging
import Bcfg2.Logger
import platform

# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser


def build_reason_kwargs(r_ent, encoding, logger):
    binary_file = False
    sensitive_file = False
    if r_ent.get('sensitive') in ['true', 'True']:
        sensitive_file = True
        rc_diff = ''
    elif r_ent.get('current_bfile', False):
        binary_file = True
        rc_diff = r_ent.get('current_bfile')
        if len(rc_diff) > 1024 * 1024:
            rc_diff = ''
        elif len(rc_diff) == 0:
            # No point in flagging binary if we have no data
            binary_file = False
    elif r_ent.get('current_bdiff', False):
        rc_diff = binascii.a2b_base64(r_ent.get('current_bdiff'))
    elif r_ent.get('current_diff', False):
        rc_diff = r_ent.get('current_diff')
    else:
        rc_diff = ''
    if not binary_file:
        try:
            rc_diff = rc_diff.decode(encoding)
        except:
            logger.error("Reason isn't %s encoded, cannot decode it" % encoding)
            rc_diff = ''
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
                current_exists=r_ent.get('current_exists', default="True").capitalize() == "True",
                current_diff=rc_diff,
                is_binary=binary_file,
                is_sensitive=sensitive_file)


def load_stats(cdata, sdata, encoding, vlevel, logger, quick=False, location=''):
    clients = {}
    [clients.__setitem__(c.name, c) \
        for c in Client.objects.all()]

    pingability = {}
    [pingability.__setitem__(n.get('name'), n.get('pingable', default='N')) \
        for n in cdata.findall('Client')]

    for node in sdata.findall('Node'):
        name = node.get('name')
        c_inst, created = Client.objects.get_or_create(name=name)
        if vlevel > 0:
            logger.info("Client %s added to db" % name)
        clients[name] = c_inst
        try:
            pingability[name]
        except KeyError:
            pingability[name] = 'N'
        for statistics in node.findall('Statistics'):
            timestamp = datetime(*strptime(statistics.get('time'))[0:6])
            ilist = Interaction.objects.filter(client=c_inst,
                                               timestamp=timestamp)
            if ilist:
                current_interaction = ilist[0]
                if vlevel > 0:
                    logger.info("Interaction for %s at %s with id %s already exists" % \
                        (c_inst.id, timestamp, current_interaction.id))
                continue
            else:
                newint = Interaction(client=c_inst,
                                     timestamp=timestamp,
                                     state=statistics.get('state',
                                                          default="unknown"),
                                     repo_rev_code=statistics.get('revision',
                                                                  default="unknown"),
                                     client_version=statistics.get('client_version',
                                                                   default="unknown"),
                                     goodcount=statistics.get('good',
                                                              default="0"),
                                     totalcount=statistics.get('total',
                                                               default="0"),
                                     server=location)
                newint.save()
                current_interaction = newint
                if vlevel > 0:
                    logger.info("Interaction for %s at %s with id %s INSERTED in to db" % (c_inst.id,
                        timestamp, current_interaction.id))

            counter_fields = {TYPE_CHOICES[0]: 0,
                              TYPE_CHOICES[1]: 0,
                              TYPE_CHOICES[2]: 0}
            pattern = [('Bad/*', TYPE_CHOICES[0]),
                       ('Extra/*', TYPE_CHOICES[2]),
                       ('Modified/*', TYPE_CHOICES[1])]
            for (xpath, type) in pattern:
                for x in statistics.findall(xpath):
                    counter_fields[type] = counter_fields[type] + 1
                    kargs = build_reason_kwargs(x, encoding, logger)

                    try:
                        rr = None
                        try:
                            rr = Reason.objects.filter(**kargs)[0]
                        except IndexError:
                            rr = Reason(**kargs)
                            rr.save()
                            if vlevel > 0:
                                logger.info("Created reason: %s" % rr.id)
                    except Exception:
                        ex = sys.exc_info()[1]
                        logger.error("Failed to create reason for %s: %s" % (x.get('name'), ex))
                        rr = Reason(current_exists=x.get('current_exists',
                                                         default="True").capitalize() == "True")
                        rr.save()

                    entry, created = Entries.objects.get_or_create(\
                        name=x.get('name'), kind=x.tag)

                    Entries_interactions(entry=entry, reason=rr,
                                         interaction=current_interaction,
                                         type=type[0]).save()
                    if vlevel > 0:
                        logger.info("%s interaction created with reason id %s and entry %s" % (xpath, rr.id, entry.id))

            # Update interaction counters
            current_interaction.bad_entries = counter_fields[TYPE_CHOICES[0]]
            current_interaction.modified_entries = counter_fields[TYPE_CHOICES[1]]
            current_interaction.extra_entries = counter_fields[TYPE_CHOICES[2]]
            current_interaction.save()

            mperfs = []
            for times in statistics.findall('OpStamps'):
                for metric, value in list(times.items()):
                    mmatch = []
                    if not quick:
                        mmatch = Performance.objects.filter(metric=metric, value=value)

                    if mmatch:
                        mperf = mmatch[0]
                    else:
                        mperf = Performance(metric=metric, value=value)
                        mperf.save()
                    mperfs.append(mperf)
            current_interaction.performance_items.add(*mperfs)

    for key in list(pingability.keys()):
        if key not in clients:
            continue
        try:
            pmatch = Ping.objects.filter(client=clients[key]).order_by('-endtime')[0]
            if pmatch.status == pingability[key]:
                pmatch.endtime = datetime.now()
                pmatch.save()
                continue
        except IndexError:
            pass
        Ping(client=clients[key], status=pingability[key],
             starttime=datetime.now(),
             endtime=datetime.now()).save()

    if vlevel > 1:
        logger.info("---------------PINGDATA SYNCED---------------------")

    #Clients are consistent

if __name__ == '__main__':
    from sys import argv
    verb = 0
    cpath = "/etc/bcfg2.conf"
    clientpath = False
    statpath = False
    syslog = False

    try:
        opts, args = getopt(argv[1:], "hvudc:s:CS", ["help",
                                                     "verbose",
                                                     "updates",
                                                     "debug",
                                                     "clients=",
                                                     "stats=",
                                                     "config=",
                                                     "syslog"])
    except GetoptError:
        mesg = sys.exc_info()[1]
        # print help information and exit:
        print("%s\nUsage:\nimportscript.py [-h] [-v] [-u] [-d] [-S] [-C bcfg2 config file] [-c clients-file] [-s statistics-file]" % (mesg))
        raise SystemExit(2)

    for o, a in opts:
        if o in ("-h", "--help"):
            print("Usage:\nimportscript.py [-h] [-v] -c <clients-file> -s <statistics-file> \n")
            print("h : help; this message")
            print("v : verbose; print messages on record insertion/skip")
            print("u : updates; print status messages as items inserted semi-verbose")
            print("d : debug; print most SQL used to manipulate database")
            print("C : path to bcfg2.conf config file.")
            print("c : clients.xml file")
            print("s : statistics.xml file")
            print("S : syslog; output to syslog")
            raise SystemExit
        if o in ["-C", "--config"]:
            cpath = a

        if o in ("-v", "--verbose"):
            verb = 1
        if o in ("-u", "--updates"):
            verb = 2
        if o in ("-d", "--debug"):
            verb = 3
        if o in ("-c", "--clients"):
            clientspath = a

        if o in ("-s", "--stats"):
            statpath = a
        if o in ("-S", "--syslog"):
            syslog = True

    logger = logging.getLogger('importscript.py')
    logging.getLogger().setLevel(logging.INFO)
    Bcfg2.Logger.setup_logging('importscript.py',
                               True,
                               syslog)

    cf = ConfigParser.ConfigParser()
    cf.read([cpath])

    if not statpath:
        try:
            statpath = "%s/etc/statistics.xml" % cf.get('server', 'repository')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            print("Could not read bcfg2.conf; exiting")
            raise SystemExit(1)
    try:
        statsdata = XML(open(statpath).read())
    except (IOError, XMLSyntaxError):
        print("StatReports: Failed to parse %s" % (statpath))
        raise SystemExit(1)

    try:
        encoding = cf.get('components', 'encoding')
    except:
        encoding = 'UTF-8'

    if not clientpath:
        try:
            clientspath = "%s/Metadata/clients.xml" % \
                          cf.get('server', 'repository')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            print("Could not read bcfg2.conf; exiting")
            raise SystemExit(1)
    try:
        clientsdata = XML(open(clientspath).read())
    except (IOError, XMLSyntaxError):
        print("StatReports: Failed to parse %s" % (clientspath))
        raise SystemExit(1)

    q = '-O3' in sys.argv
    # Be sure the database is ready for new schema
    update_database()
    load_stats(clientsdata,
               statsdata,
               encoding,
               verb,
               logger,
               quick=q,
               location=platform.node())
