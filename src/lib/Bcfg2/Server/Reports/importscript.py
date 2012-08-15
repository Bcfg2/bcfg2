#! /usr/bin/env python
"""
Imports statistics.xml and clients.xml files in to database backend for
new statistics engine
"""

import binascii
import os
import sys
import traceback
try:
    import Bcfg2.settings
except Exception:
    e = sys.exc_info()[1]
    sys.stderr.write("Failed to load configuration settings. %s\n" % e)
    sys.exit(1)

project_directory = os.path.dirname(Bcfg2.settings.__file__)
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
from django.db import connection, transaction
from Bcfg2.Server.Plugins.Metadata import ClientMetadata
import logging
import Bcfg2.Logger
import platform

# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser


def build_reason_kwargs(r_ent, encoding, logger):
    binary_file = False
    sensitive_file = False
    unpruned_entries = ''
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
    # detect unmanaged entries in pruned directories
    if r_ent.get('prune', 'false') == 'true' and r_ent.get('qtest'):
        unpruned_elist = [e.get('path') for e in r_ent.findall('Prune')]
        unpruned_entries = "\n".join(unpruned_elist)
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
                is_sensitive=sensitive_file,
                unpruned=unpruned_entries)

def _fetch_reason(elem, kargs, logger):
    try:
        rr = None
        try:
            rr = Reason.objects.filter(**kargs)[0]
        except IndexError:
            rr = Reason(**kargs)
            rr.save()
            logger.info("Created reason: %s" % rr.id)
    except Exception:
        ex = sys.exc_info()[1]
        logger.error("Failed to create reason for %s: %s" % (elem.get('name'), ex))
        rr = Reason(current_exists=elem.get('current_exists',
            default="True").capitalize() == "True")
        rr.save()
    return rr


def load_stats(sdata, encoding, vlevel, logger, quick=False, location=''):
    for node in sdata.findall('Node'):
        name = node.get('name')
        for statistics in node.findall('Statistics'):
            try:
                load_stat(name, statistics, encoding, vlevel, logger, quick, location)
            except:
                logger.error("Failed to create interaction for %s: %s" %
                    (name, traceback.format_exc().splitlines()[-1]))

@transaction.commit_on_success
def load_stat(cobj, statistics, encoding, vlevel, logger, quick, location):
    if isinstance(cobj, ClientMetadata):
        client_name = cobj.hostname
    else:
        client_name = cobj
    client, created = Client.objects.get_or_create(name=client_name)
    if created and vlevel > 0:
        logger.info("Client %s added to db" % client_name)

    timestamp = datetime(*strptime(statistics.get('time'))[0:6])
    ilist = Interaction.objects.filter(client=client,
                                       timestamp=timestamp)
    if ilist:
        current_interaction = ilist[0]
        if vlevel > 0:
            logger.info("Interaction for %s at %s with id %s already exists" % \
                (client.id, timestamp, current_interaction.id))
        return
    else:
        newint = Interaction(client=client,
                             timestamp=timestamp,
                             state=statistics.get('state',
                                                  default="unknown"),
                             repo_rev_code=statistics.get('revision',
                                                          default="unknown"),
                             goodcount=statistics.get('good',
                                                      default="0"),
                             totalcount=statistics.get('total',
                                                       default="0"),
                             server=location)
        newint.save()
        current_interaction = newint
        if vlevel > 0:
            logger.info("Interaction for %s at %s with id %s INSERTED in to db" % (client.id,
                timestamp, current_interaction.id))

    if isinstance(cobj, ClientMetadata):
        try:
            imeta = InteractionMetadata(interaction=current_interaction)
            profile, created = Group.objects.get_or_create(name=cobj.profile)
            imeta.profile = profile
            imeta.save() # save here for m2m

            #FIXME - this should be more efficient
            group_set = []
            for group_name in cobj.groups:
                group, created = Group.objects.get_or_create(name=group_name)
                if created:
                    logger.debug("Added group %s" % group)
                imeta.groups.add(group)
            for bundle_name in cobj.bundles:
                bundle, created = Bundle.objects.get_or_create(name=bundle_name)
                if created:
                    logger.debug("Added bundle %s" % bundle)
                imeta.bundles.add(bundle)
            imeta.save()
        except:
            logger.error("Failed to save interaction metadata for %s: %s" %
                (client_name, traceback.format_exc().splitlines()[-1]))


    entries_cache = {}
    [entries_cache.__setitem__((e.kind, e.name), e) \
        for e in Entries.objects.all()]
    counter_fields = {TYPE_BAD: 0,
                      TYPE_MODIFIED: 0,
                      TYPE_EXTRA: 0}
    pattern = [('Bad/*', TYPE_BAD),
               ('Extra/*', TYPE_EXTRA),
               ('Modified/*', TYPE_MODIFIED)]
    for (xpath, type) in pattern:
        for x in statistics.findall(xpath):
            counter_fields[type] = counter_fields[type] + 1
            rr = _fetch_reason(x, build_reason_kwargs(x, encoding, logger), logger)

            try:
                entry = entries_cache[(x.tag, x.get('name'))]
            except KeyError:
                entry, created = Entries.objects.get_or_create(\
                    name=x.get('name'), kind=x.tag)

            Entries_interactions(entry=entry, reason=rr,
                                 interaction=current_interaction,
                                 type=type).save()
            if vlevel > 0:
                logger.info("%s interaction created with reason id %s and entry %s" % (xpath, rr.id, entry.id))

    # add good entries
    good_reason = None
    for x in statistics.findall('Good/*'):
        if good_reason == None:
            # Do this once.  Really need to fix Reasons...
            good_reason = _fetch_reason(x, build_reason_kwargs(x, encoding, logger), logger)
        try:
            entry = entries_cache[(x.tag, x.get('name'))]
        except KeyError:
            entry, created = Entries.objects.get_or_create(\
                name=x.get('name'), kind=x.tag)
        Entries_interactions(entry=entry, reason=good_reason,
                             interaction=current_interaction,
                             type=TYPE_GOOD).save()
        if vlevel > 0:
            logger.info("%s interaction created with reason id %s and entry %s" % (xpath, good_reason.id, entry.id))

    # Update interaction counters
    current_interaction.bad_entries = counter_fields[TYPE_BAD]
    current_interaction.modified_entries = counter_fields[TYPE_MODIFIED]
    current_interaction.extra_entries = counter_fields[TYPE_EXTRA]
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
        print("%s\nUsage:\nimportscript.py [-h] [-v] [-u] [-d] [-S] [-C bcfg2 config file] [-s statistics-file]" % (mesg))
        raise SystemExit(2)

    for o, a in opts:
        if o in ("-h", "--help"):
            print("Usage:\nimportscript.py [-h] [-v] -s <statistics-file> \n")
            print("h : help; this message")
            print("v : verbose; print messages on record insertion/skip")
            print("u : updates; print status messages as items inserted semi-verbose")
            print("d : debug; print most SQL used to manipulate database")
            print("C : path to bcfg2.conf config file.")
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
            print("DeprecationWarning: %s is no longer used" % o)

        if o in ("-s", "--stats"):
            statpath = a
        if o in ("-S", "--syslog"):
            syslog = True

    logger = logging.getLogger('importscript.py')
    logging.getLogger().setLevel(logging.INFO)
    Bcfg2.Logger.setup_logging('importscript.py',
                               True,
                               syslog, level=logging.INFO)

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

    q = '-O3' in sys.argv

    # don't load this at the top.  causes a circular import error
    from Bcfg2.Server.SchemaUpdater import update_database, UpdaterError
    # Be sure the database is ready for new schema
    try:
        update_database()
    except UpdaterError:
        raise SystemExit(1)
    load_stats(statsdata,
               encoding,
               verb,
               logger,
               quick=q,
               location=platform.node())
