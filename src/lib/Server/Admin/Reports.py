'''Admin interface for dynamic reports'''
import Bcfg2.Logger
import Bcfg2.Server.Admin
import datetime
import os
import logging
import pickle
import platform
import sys
import traceback
import Bcfg2.Options
from lxml.etree import XML, XMLSyntaxError

# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser

# FIXME: Remove when server python dep is 2.5 or greater
if sys.version_info >= (2, 5):
    from hashlib import md5
else:
    from md5 import md5

# Prereq issues can be signaled with ImportError, so no try needed
# FIXME - settings file uses a hardcoded path for /etc/bcfg2.conf
import Bcfg2.Server.Reports.settings

# Load django and reports stuff _after_ we know we can load settings
import django.core.management
from Bcfg2.Server.Reports.importscript import load_stats
from Bcfg2.Server.Reports.updatefix import update_database
from Bcfg2.Server.Reports.utils import *

project_directory = os.path.dirname(Bcfg2.Server.Reports.settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()

# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name
from django.db import connection, transaction

from Bcfg2.Server.Reports.reports.models import Client, Interaction, Entries, \
                                Entries_interactions, Performance, \
                                Reason, Ping


def printStats(fn):
    """
    Print db stats.

    Decorator for purging.  Prints database statistics after a run.
    """
    def print_stats(self, *data):
        start_client = Client.objects.count()
        start_i = Interaction.objects.count()
        start_ei = Entries_interactions.objects.count()
        start_perf = Performance.objects.count()
        start_ping = Ping.objects.count()

        fn(self, *data)

        self.log.info("Clients removed: %s" %
                      (start_client - Client.objects.count()))
        self.log.info("Interactions removed: %s" %
                      (start_i - Interaction.objects.count()))
        self.log.info("Interactions->Entries removed: %s" %
                      (start_ei - Entries_interactions.objects.count()))
        self.log.info("Metrics removed: %s" %
                      (start_perf - Performance.objects.count()))
        self.log.info("Ping metrics removed: %s" %
                      (start_ping - Ping.objects.count()))

    return print_stats


class Reports(Bcfg2.Server.Admin.Mode):
    '''Admin interface for dynamic reports'''
    __shorthelp__ = "Manage dynamic reports"
    __longhelp__ = (__shorthelp__)
    django_commands = ['syncdb', 'sqlall', 'validate']
    __usage__ = ("bcfg2-admin reports [command] [options]\n"
                 "    -v|--verbose         Be verbose\n"
                 "    -q|--quiet           Print only errors\n"
                 "\n"
                 "  Commands:\n"
                 "    init                 Initialize the database\n"
                 "    load_stats           Load statistics data\n"
                 "      -s|--stats         Path to statistics.xml file\n"
                 "      -c|--clients-file  Path to clients.xml file\n"
                 "      -O3                Fast mode.  Duplicates data!\n"
                 "    purge                Purge records\n"
                 "      --client [n]       Client to operate on\n"
                 "      --days   [n]       Records older then n days\n"
                 "      --expired          Expired clients only\n"
                 "    scrub                Scrub the database for duplicate reasons and orphaned entries\n"
                 "    update               Apply any updates to the reporting database\n"
                 "\n"
                 "  Django commands:\n    "
                 "\n    ".join(django_commands))

    def __init__(self):
        Bcfg2.Server.Admin.Mode.__init__(self)
        self.log.setLevel(logging.INFO)
        self.django_commands = ['syncdb', 'sqlall', 'validate']
        self.__usage__ = self.__usage__ + "  Django commands:\n    " + \
             "\n    ".join(self.django_commands)
        Bcfg2.Options.add_options(
            Bcfg2.Options.VERBOSE,
            Option('-q', '--quiet', action='store_true'),
            Option('command',
                choices=['init', 'load_stats', 'purge', 'scrub', 'update'] + self.django_commands,
                help='Command to execute')
        )
        
        args = Bcfg2.Options.bootstrap()
        if args.command == 'load_stats':
            Bcfg2.Options.add_options(
                Option('-s', '--stats', help='Path to statistics.xml file'),
                Option('-c', '--clients-file', help='Path to clients.xml file'),
                Option('-O3', help='Fast mode. Duplicates data!', dest='quick', action='store_true')
            )
        elif args.command == 'purge':
            Bcfg2.Options.add_options(
                Option('--client', help='Client to operate on'),
                Option('--days', type=int, help='Records older than n days', metavar='[n]'),
                Option('--expired', help='Expired clients only')
            )

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)

        verb = 0

        if args.verbose:
            self.log.setLevel(logging.DEBUG)
            verb = 1
        if args.quiet:
            self.log.setLevel(logging.WARNING)

        # FIXME - dry run

        if args.command in self.django_commands:
            self.django_command_proxy(args.command)
        elif args.command == 'scrub':
            self.scrub()
        elif args.command == 'init':
            update_database()
        elif args.command == 'update':
            update_database()
        elif args.command == 'load_stats':
            self.load_stats(args.stats, args.clients, verb, args.quick)
        elif args.command == 'purge':
            if args.days:
                maxdate = datetime.datetime.now() - datetime.timedelta(days=args.days)
            else:
                maxdate = None

            if args.expired:
                self.purge_expired(maxdate)
            else:
                self.purge(args.client, maxdate, None)

    @transaction.commit_on_success
    def scrub(self):
        ''' Perform a thorough scrub and cleanup of the database '''

        # Currently only reasons are a problem
        try:
            start_count = Reason.objects.count()
        except Exception:
            e = sys.exc_info()[1]
            self.log.error("Failed to load reason objects: %s" % e)
            return
        dup_reasons = []

        cmp_reasons = dict()
        batch_update = []
        for reason in BatchFetch(Reason.objects):
            ''' Loop through each reason and create a key out of the data. \
                This lets us take advantage of a fast hash lookup for \
                comparisons '''
            id = reason.id
            reason.id = None
            key = md5(pickle.dumps(reason)).hexdigest()
            reason.id = id

            if key in cmp_reasons:
                self.log.debug("Update interactions from %d to %d" \
                                    % (reason.id, cmp_reasons[key]))
                dup_reasons.append([reason.id])
                batch_update.append([cmp_reasons[key], reason.id])
            else:
                cmp_reasons[key] = reason.id
            self.log.debug("key %d" % reason.id)

        self.log.debug("Done with updates, deleting dupes")
        try:
            cursor = connection.cursor()
            cursor.executemany('update reports_entries_interactions set reason_id=%s where reason_id=%s', batch_update)
            cursor.executemany('delete from reports_reason where id = %s', dup_reasons)
            transaction.set_dirty()
        except Exception:
            ex = sys.exc_info()[1]
            self.log.error("Failed to delete reasons: %s" % ex)
            raise

        self.log.info("Found %d dupes out of %d" % (len(dup_reasons), start_count))

        # Cleanup orphans
        start_count = Reason.objects.count()
        Reason.prune_orphans()
        self.log.info("Pruned %d Reason records" % (start_count - Reason.objects.count()))

        start_count = Entries.objects.count()
        Entries.prune_orphans()
        self.log.info("Pruned %d Entries records" % (start_count - Entries.objects.count()))

    def django_command_proxy(self, command):
        '''Call a django command'''
        if command == 'sqlall':
            django.core.management.call_command(command, 'reports')
        else:
            django.core.management.call_command(command)

    def load_stats(self, stats_file=None, clientspath=None, verb=0, quick=False):
        '''Load statistics data into the database'''
        location = ''

        if not stats_file:
            try:
                stats_file = "%s/etc/statistics.xml" % self.cfp.get('server', 'repository')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.errExit("Could not read bcfg2.conf; exiting")
        try:
            statsdata = XML(open(stats_file).read())
        except (IOError, XMLSyntaxError):
            self.errExit("StatReports: Failed to parse %s" % (stats_file))

        try:
            encoding = self.cfp.get('components', 'encoding')
        except:
            encoding = 'UTF-8'

        if not clientspath:
            try:
                clientspath = "%s/Metadata/clients.xml" % \
                          self.cfp.get('server', 'repository')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.errExit("Could not read bcfg2.conf; exiting")
        try:
            clientsdata = XML(open(clientspath).read())
        except (IOError, XMLSyntaxError):
            self.errExit("StatReports: Failed to parse %s" % (clientspath))

        try:
            load_stats(clientsdata,
                       statsdata,
                       encoding,
                       verb,
                       self.log,
                       quick=quick,
                       location=platform.node())
        except:
            pass

    @printStats
    def purge(self, client=None, maxdate=None, state=None):
        '''Purge historical data from the database'''

        filtered = False  # indicates whether or not a client should be deleted

        if not client and not maxdate and not state:
            self.errExit("Reports.prune: Refusing to prune all data")

        ipurge = Interaction.objects
        if client:
            try:
                cobj = Client.objects.get(name=client)
                ipurge = ipurge.filter(client=cobj)
            except Client.DoesNotExist:
                self.log.error("Client %s not in database" % client)
                raise SystemExit(-1)
            self.log.debug("Filtering by client: %s" % client)

        if maxdate:
            filtered = True
            if not isinstance(maxdate, datetime.datetime):
                raise TypeError("maxdate is not a DateTime object")
            self.log.debug("Filtering by maxdate: %s" % maxdate)
            ipurge = ipurge.filter(timestamp__lt=maxdate)

            # Handle ping data as well
            ping = Ping.objects.filter(endtime__lt=maxdate)
            if client:
                ping = ping.filter(client=cobj)
            ping.delete()

        if state:
            filtered = True
            if state not in ('dirty', 'clean', 'modified'):
                raise TypeError("state is not one of the following values " + \
                                "('dirty','clean','modified')")
            self.log.debug("Filtering by state: %s" % state)
            ipurge = ipurge.filter(state=state)

        count = ipurge.count()
        rnum = 0
        try:
            while rnum < count:
                grp = list(ipurge[:1000].values("id"))
                # just in case...
                if not grp:
                    break
                Interaction.objects.filter(id__in=[x['id'] for x in grp]).delete()
                rnum += len(grp)
                self.log.debug("Deleted %s of %s" % (rnum, count))
        except:
            self.log.error("Failed to remove interactions")
            (a, b, c) = sys.exc_info()
            msg = traceback.format_exception(a, b, c, limit=2)[-1][:-1]
            del a, b, c
            self.log.error(msg)

        # bulk operations bypass the Interaction.delete method
        self.log.debug("Pruning orphan Performance objects")
        Performance.prune_orphans()
        self.log.debug("Pruning orphan Reason objects")
        Reason.prune_orphans()

        if client and not filtered:
            '''Delete the client, ping data is automatic'''
            try:
                self.log.debug("Purging client %s" % client)
                cobj.delete()
            except:
                self.log.error("Failed to delete client %s" % client)
                (a, b, c) = sys.exc_info()
                msg = traceback.format_exception(a, b, c, limit=2)[-1][:-1]
                del a, b, c
                self.log.error(msg)

    @printStats
    def purge_expired(self, maxdate=None):
        '''Purge expired clients from the database'''

        if maxdate:
            if not isinstance(maxdate, datetime.datetime):
                raise TypeError("maxdate is not a DateTime object")
            self.log.debug("Filtering by maxdate: %s" % maxdate)
            clients = Client.objects.filter(expiration__lt=maxdate)
        else:
            clients = Client.objects.filter(expiration__isnull=False)

        for client in clients:
            self.log.debug("Purging client %s" % client)
            Interaction.objects.filter(client=client).delete()
            client.delete()
        self.log.debug("Pruning orphan Performance objects")
        Performance.prune_orphans()
