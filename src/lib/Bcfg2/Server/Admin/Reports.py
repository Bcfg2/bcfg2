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

from Bcfg2.Compat import md5

from Bcfg2 import settings

# Load django and reports stuff _after_ we know we can load settings
from django.core import management
from Bcfg2.Reporting.utils import *

project_directory = os.path.dirname(settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()

# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name
from django.db import connection, transaction

from Bcfg2.Reporting.models import Client, Interaction, \
                                Performance


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

        fn(self, *data)

        self.log.info("Clients removed: %s" %
                      (start_client - Client.objects.count()))
        self.log.info("Interactions removed: %s" %
                      (start_i - Interaction.objects.count()))
        self.log.info("Interactions->Entries removed: %s" %
                      (start_ei - 0))
        #              (start_ei - Entries_interactions.objects.count()))
        self.log.info("Metrics removed: %s" %
                      (start_perf - Performance.objects.count()))

    return print_stats


class Reports(Bcfg2.Server.Admin.Mode):
    '''Admin interface for dynamic reports'''
    __shorthelp__ = "Manage dynamic reports"
    __longhelp__ = (__shorthelp__)
    django_commands = ['dbshell', 'shell', 'syncdb', 'sqlall', 'validate']
    __usage__ = ("bcfg2-admin reports [command] [options]\n"
                 "\n"
                 "  Commands:\n"
                 "    init                 Initialize the database\n"
                 "    purge                Purge records\n"
                 "      --client [n]       Client to operate on\n"
                 "      --days   [n]       Records older then n days\n"
                 "      --expired          Expired clients only\n"
                 "    scrub                Scrub the database for duplicate reasons and orphaned entries\n"
                 "    update               Apply any updates to the reporting database\n"
                 "\n"
                 "  Django commands:\n    " \
                 + "\n    ".join(django_commands))

    def __init__(self, setup):
        Bcfg2.Server.Admin.Mode.__init__(self, setup)
        try:
            import south
        except ImportError:
            print "Django south is required for Reporting"
            raise SystemExit(-3)

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) == 0 or args[0] == '-h':
            print(self.__usage__)
            raise SystemExit(0)

        # FIXME - dry run

        if args[0] in self.django_commands:
            self.django_command_proxy(args[0])
        elif args[0] == 'scrub':
            self.scrub()
        elif args[0] in ['init', 'update']:
            if self.setup['verbose'] or self.setup['debug']:
                vrb = 2
            else:
                vrb = 0
            try:
                management.call_command("syncdb", verbosity=vrb)
                management.call_command("migrate", verbosity=vrb)
            except:
                print("Update failed: %s" % traceback.format_exc().splitlines()[-1])
                raise SystemExit(-1)
        elif args[0] == 'purge':
            expired = False
            client = None
            maxdate = None
            state = None
            i = 1
            while i < len(args):
                if args[i] == '-c' or args[i] == '--client':
                    if client:
                        self.errExit("Only one client per run")
                    client = args[i + 1]
                    print(client)
                    i = i + 1
                elif args[i] == '--days':
                    if maxdate:
                        self.errExit("Max date specified multiple times")
                    try:
                        maxdate = datetime.datetime.now() - datetime.timedelta(days=int(args[i + 1]))
                    except:
                        self.log.error("Invalid number of days: %s" % args[i + 1])
                        raise SystemExit(-1)
                    i = i + 1
                elif args[i] == '--expired':
                    expired = True
                i = i + 1
            if expired:
                if state:
                    self.log.error("--state is not valid with --expired")
                    raise SystemExit(-1)
                self.purge_expired(maxdate)
            else:
                self.purge(client, maxdate, state)
        else:
            print("Unknown command: %s" % args[0])

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

        #start_count = Entries.objects.count()
        #Entries.prune_orphans()
        #self.log.info("Pruned %d Entries records" % (start_count - Entries.objects.count()))

    def django_command_proxy(self, command):
        '''Call a django command'''
        if command == 'sqlall':
            django.core.management.call_command(command, 'reports')
        else:
            django.core.management.call_command(command)


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

        if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
            grp_limit = 100
        else:
            grp_limit = 1000
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
                grp = list(ipurge[:grp_limit].values("id"))
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
