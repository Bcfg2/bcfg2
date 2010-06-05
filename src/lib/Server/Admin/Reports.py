'''Admin interface for dynamic reports'''
import Bcfg2.Logger
import Bcfg2.Server.Admin
import ConfigParser
import os
import logging
import pickle
import platform
import sys
from Bcfg2.Server.Reports.importscript import load_stats
from Bcfg2.Server.Reports.updatefix import update_database
from Bcfg2.Server.Reports.utils import *
from lxml.etree import XML, XMLSyntaxError

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

# Load django
import django.core.management

# FIXME - settings file uses a hardcoded path for /etc/bcfg2.conf
try:
    import Bcfg2.Server.Reports.settings
except Exception, e:
    sys.stderr.write("Failed to load configuration settings. %s\n" % e)
    sys.exit(1)

project_directory = os.path.dirname(Bcfg2.Server.Reports.settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()

# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name
from django.db import connection

from Bcfg2.Server.Reports.reports.models import Client, Interaction, Entries, \
				Entries_interactions, Performance, \
				Reason, Ping, TYPE_CHOICES, InternalDatabaseVersion

class Reports(Bcfg2.Server.Admin.Mode):
    '''Admin interface for dynamic reports'''
    __shorthelp__ = "Manage dynamic reports"
    __longhelp__ = (__shorthelp__)
    __usage__ = ("bcfg2-admin reports [command] [options]\n"
                 "    -v|--verbose         Be verbose\n"
                 "    -q|--quiet           Print only errors\n"
                 "\n"
                 "  Commands:\n"
                 "    load_stats           Load statistics data\n"
                 "      -s|--stats         Path to statistics.xml file\n"
                 "      -c|--clients-file  Path to clients.xml file\n"
                 "      -O3                Fast mode.  Duplicates data!\n"
                 "    scrub                Scrub the database for duplicate reasons\n"
                 "    update               Apply any updates to the reporting database\n"
                 "\n")

    def __init__(self, cfile):
        Bcfg2.Server.Admin.Mode.__init__(self, cfile)
        self.log.setLevel(logging.INFO)
        self.django_commands = [ 'syncdb', 'sqlall', 'validate' ]
        self.__usage__ = self.__usage__ + "  Django commands:\n    " + \
             "\n    ".join(self.django_commands)

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) == 0 or args[0] == '-h':
            print(self.__usage__)
            raise SystemExit(0)

        verb = 0

        if '-v' in args or '--verbose' in args:
            self.log.setLevel(logging.DEBUG)
            verb = 1
        if '-q' in args or '--quiet' in args:
            self.log.setLevel(logging.WARNING)

        # FIXME - dry run

        if args[0] in self.django_commands:
            self.django_command_proxy(args[0])
        elif args[0] == 'scrub':
            self.scrub()
        elif args[0] == 'update':
            update_database()
        elif args[0] == 'load_stats':
            quick = '-O3' in args
            stats_file=None
            clients_file=None
            i=1
            while i < len(args):
                if args[i] == '-s' or args[i] == '--stats':
                    stats_file = args[i+1]
                    if stats_file[0] == '-':
                        self.errExit("Invalid statistics file: %s" % stats_file)
                elif args[i] == '-c' or args[i] == '--clients-file':
                    clients_file = args[i+1]
                    if clients_file[0] == '-':
                        self.errExit("Invalid clients file: %s" % clients_file)
                i = i + 1
            self.load_stats(stats_file, clients_file, verb, quick)
        else:
            print "Unknown command: %s" % args[0]

    def scrub(self):
        ''' Perform a thorough scrub and cleanup of the database '''

        # Currently only reasons are a problem
        try:
            start_count = Reason.objects.count()
        except Exception, e:
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
            key=md5(pickle.dumps(reason)).hexdigest()
            reason.id = id

            if key in cmp_reasons:
                self.log.debug("Update interactions from %d to %d" \
                                    % (reason.id, cmp_reasons[key]))
                dup_reasons.append(reason.id)
                batch_update.append([cmp_reasons[key], reason.id])
            else:
                cmp_reasons[key] = reason.id
            self.log.debug("key %d" % reason.id)
    
        self.log.debug("Done with updates, deleting dupes")
        try:
            cursor = connection.cursor()
            cursor.executemany('update reports_entries_interactions set reason_id=%s where reason_id=%s', batch_update)
            cursor.executemany('delete from reports_reason where id = %s', dup_reasons)
        except Exception, ex:
            self.log.error("Failed to delete reasons: %s" % ex)

        self.log.info("Found %d dupes out of %d" % (len(dup_reasons), start_count))

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
            self.errExit("StatReports: Failed to parse %s"%(stats_file))

        if not clientspath:
            try:
                clientspath = "%s/Metadata/clients.xml" % \
                          self.cfp.get('server', 'repository')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.errExit("Could not read bcfg2.conf; exiting")
        try:
            clientsdata = XML(open(clientspath).read())
        except (IOError, XMLSyntaxError):
            self.errExit("StatReports: Failed to parse %s"%(clientspath))

        load_stats(clientsdata, statsdata, verb, self.log, quick=quick, location=platform.node())

