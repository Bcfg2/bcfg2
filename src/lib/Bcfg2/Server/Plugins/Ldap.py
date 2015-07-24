""" A plugin to fetch data from a LDAP directory """

import imp
import os
import sys
import time
import traceback
import Bcfg2.Options
import Bcfg2.Server.Plugin
from Bcfg2.Logger import Debuggable
from Bcfg2.Utils import ClassName, safe_module_name

try:
    import ldap
    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False


class ConfigFile(Bcfg2.Server.Plugin.FileBacked):
    """ Config file for the Ldap plugin  """

    def __init__(self, name, core):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, name)
        self.core = core
        self.queries = list()
        self.fam.AddMonitor(name, self)

    def Index(self):
        """ Get the queries from the config file """
        try:
            module = imp.load_source(safe_module_name('Ldap', self.name),
                                     self.name)
        except:  # pylint: disable=W0702
            err = sys.exc_info()[1]
            self.logger.error("Ldap: Failed to import %s: %s" %
                              (self.name, err))
            return

        if not hasattr(module, "__queries__"):
            self.logger.error("Ldap: %s has no __queries__ list" % self.name)
            return

        self.queries = list()
        for query in module.__queries__:
            try:
                self.queries.append(getattr(module, query))
            except AttributeError:
                self.logger.warning(
                    "Ldap: %s exports %s, but has no such attribute" %
                    (self.name, query))

        if self.core.metadata_cache_mode in ['cautious', 'aggressive']:
            self.core.metadata_cache.expire()


class Ldap(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.ClientRunHooks,
           Bcfg2.Server.Plugin.Connector):
    """ The Ldap plugin allows adding data from an LDAP server
    to your metadata. """

    experimental = True

    options = [
        Bcfg2.Options.Option(
            cf=('ldap', 'retries'), type=int, default=3,
            help='The number of times to retry reaching the '
                 'LDAP server if a connection is broken'),
        Bcfg2.Options.Option(
            cf=('ldap', 'retry_delay'), type=float, default=5.0,
            help='The time in seconds betreen retries')]

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)

        if not HAS_LDAP:
            msg = "Python ldap module is required for Ldap plugin"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)

        self.config = ConfigFile(os.path.join(self.data, 'config.py'))

    def get_additional_data(self, metadata):
        query = None
        try:
            data = {}
            self.debug_log("Found queries %s" % self.config.queries)
            for query_class in self.config.queries:
                query = query_class()
                if query.is_applicable(metadata):
                    self.debug_log("Processing query '%s'" % query.name)
                    data[query.name] = query.get_result(metadata)
                else:
                    self.debug_log("query '%s' not applicable to host '%s'" %
                                   (query.name, metadata.hostname))
            return data
        except:  # pylint: disable=W0702
            if hasattr(query, "name"):
                self.logger.error(
                    "Exception during processing of query named '%s', query "
                    "results will be empty and may cause bind failures" %
                    query.name)
            for line in traceback.format_exc().split('\n'):
                self.logger.error(line)
            return {}

    def start_client_run(self, metadata):
        if self.core.metadata_cache_mode == 'aggressive':
            self.logger.warning("Ldap is incompatible with aggressive "
                                "client metadata caching, try 'cautious' "
                                "or 'initial'")
        self.core.metadata_cache.expire(metadata.hostname)


class LdapConnection(Debuggable):
    """ Connection to an LDAP server. """

    __scopes__ = {
        'base': ldap.SCOPE_BASE,
        'one': ldap.SCOPE_ONELEVEL,
        'sub': ldap.SCOPE_SUBTREE,
    }

    def __init__(self, host="localhost", port=389, binddn=None,
                 bindpw=None):
        Debuggable.__init__(self)

        self.host = host
        self.port = port
        self.binddn = binddn
        self.bindpw = bindpw
        self.conn = None

    def __del__(self):
        """ Disconnection if the instance is destroyed. """
        self.disconnect()

    def disconnect(self):
        """ If a connection to an LDAP server is available, disconnect it. """
        if self.conn:
            self.conn.unbund()
            self.conn = None

    def connect(self):
        """ Open a connection to the configured LDAP server, and do a simple
        bind ff both binddn and bindpw are set. """
        self.disconnect()
        self.conn = ldap.initialize(self.url)
        if self.binddn is not None and self.bindpw is not None:
            self.conn.simple_bind_s(self.binddn, self.bindpw)

    def run_query(self, query):
        """ Connect to the server and execute the query. If the server is
        down, wait the configured amount and try to reconnect.

        :param query: The query to execute on the LDAP server.
        :type query: Bcfg.Server.Plugins.Ldap.LdapQuery
        """
        for attempt in range(Bcfg2.Options.setup.ldap_retries + 1):
            try:
                if not self.conn:
                    self.connect()

                return self.conn.search_s(
                    query.base, self.__scopes__[query.scope],
                    query.filter.replace('\\', '\\\\'), query.attrs)

            except ldap.SERVER_DOWN:
                self.conn = None
                self.logger.error(
                    "LdapConnection: Server %s down. Retry %d/%d in %.2fs." %
                    (self.url, attempt + 1, Bcfg2.Options.setup.ldap_retries,
                     Bcfg2.Options.setup.ldap_retry_delay))
                time.sleep(Bcfg2.Options.setup.ldap_retry_delay)

        return None

    @property
    def url(self):
        """ The URL of the LDAP server. """
        return "ldap://%s:%d" % (self.host, self.port)


class LdapQuery(object):
    """ Query referencing an LdapConnection and providing several
    methods for query manipulation. """

    #: Name of the Query, used to register it in additional data.
    name = ClassName()

    base = ""
    scope = "sub"
    filter = "(objectClass=*)"
    attrs = None
    connection = None
    result = None

    def __unicode__(self):
        return "LdapQuery: %s" % self.name

    def is_applicable(self, metadata):  # pylint: disable=W0613
        """ Check is the query should be executed for a given metadata
        object.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        return True

    def prepare_query(self, metadata, **kwargs):  # pylint: disable=W0613
        """ Prepares the query based on the client metadata. You can
        for example modify the filter based on the client hostname.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        pass

    def process_result(self, metadata, **kwargs):  # pylint: disable=W0613
        """ Post-process the query result.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        """
        return self.result

    def get_result(self, metadata, **kwargs):
        """ Handle the perparation, execution and processing of the query.

        :param metadata: The client metadata
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :raises: :class:`Bcfg2.Server.Plugin.exceptions.PluginExecutionError`
        """

        if self.connection is not None:
            self.prepare_query(metadata, **kwargs)
            self.result = self.connection.run_query(self)
            self.result = self.process_result(metadata, **kwargs)
        else:
            raise Bcfg2.Server.Plugin.PluginExecutionError(
                'No connection defined for %s' % self.name)

        return self.result
