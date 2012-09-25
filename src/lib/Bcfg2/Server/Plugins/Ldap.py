import imp
import logging
import sys
import time
import traceback
import Bcfg2.Options
import Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.Ldap')

try:
    import ldap
except ImportError:
    logger.error("Unable to load ldap module. Is python-ldap installed?")
    raise ImportError

# time in seconds between retries after failed LDAP connection
RETRY_DELAY = 5
# how many times to try reaching the LDAP server if a connection is broken
# at the very minimum, one retry is needed to handle a restarted LDAP daemon
RETRY_COUNT = 3

SCOPE_MAP = {
    "base": ldap.SCOPE_BASE,
    "one": ldap.SCOPE_ONELEVEL,
    "sub": ldap.SCOPE_SUBTREE,
}

LDAP_QUERIES = []


def register_query(query):
    LDAP_QUERIES.append(query)


class ConfigFile(Bcfg2.Server.Plugin.FileBacked):
    """
    Config file for the Ldap plugin

    The config file cannot be 'parsed' in the traditional sense as we would
    need some serious type checking ugliness to just get the LdapQuery
    subclasses. The alternative would be to have the user create a list with
    a predefined name that contains all queries.
    The approach implemented here is having the user call a registering
    decorator that updates a global variable in this module.
    """
    def __init__(self, filename, fam):
        self.filename = filename
        Bcfg2.Server.Plugin.FileBacked.__init__(self, self.filename)
        fam.AddMonitor(self.filename, self)

    def Index(self):
        """
        Reregisters the queries in the config file

        The config will take care of actually registering the queries,
        so we just load it once and don't keep it.
        """
        global LDAP_QUERIES
        LDAP_QUERIES = []
        imp.load_source("ldap_cfg", self.filename)


class Ldap(Bcfg2.Server.Plugin.Plugin, Bcfg2.Server.Plugin.Connector):
    """
    The Ldap plugin allows adding data from an LDAP server to your metadata.
    """
    name = "Ldap"
    experimental = True
    debug_flag = False

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.config = ConfigFile(self.data + "/config.py", core.fam)

    def debug_log(self, message, flag = None):
        if (flag is None) and self.debug_flag or flag:
            self.logger.error(message)

    def get_additional_data(self, metadata):
        query = None
        try:
            data = {}
            self.debug_log("LdapPlugin debug: found queries " +
                                              str(LDAP_QUERIES))
            for QueryClass in LDAP_QUERIES:
                query = QueryClass()
                if query.is_applicable(metadata):
                    self.debug_log("LdapPlugin debug: processing query '" +
                                                           query.name + "'")
                    data[query.name] = query.get_result(metadata)
                else:
                    self.debug_log("LdapPlugin debug: query '" + query.name +
                        "' not applicable to host '" + metadata.hostname + "'")
            return data
        except Exception:
            if hasattr(query, "name"):
                logger.error("LdapPlugin error: " +
                       "Exception during processing of query named '" +
                                                      str(query.name) +
                                     "', query results will be empty" +
                                       " and may cause bind failures")
            for line in traceback.format_exception(sys.exc_info()[0],
                                                   sys.exc_info()[1],
                                                   sys.exc_info()[2]):
                logger.error("LdapPlugin error: " +
                                                 line.replace("\n", ""))
            return {}

class LdapConnection(object):
    """
    Connection to an LDAP server.
    """
    def __init__(self, host = "localhost", port = 389,
                       binddn = None, bindpw = None):
        self.host = host
        self.port = port
        self.binddn = binddn
        self.bindpw = bindpw
        self.conn = None

    def __del__(self):
        if self.conn:
            self.conn.unbind()

    def init_conn(self):
        self.conn = ldap.initialize(self.url)
        if self.binddn is not None and self.bindpw is not None:
            self.conn.simple_bind_s(self.binddn, self.bindpw)

    def run_query(self, query):
        result = None
        for attempt in range(RETRY_COUNT + 1):
            if attempt >= 1:
                logger.error("LdapPlugin error: " +
                    "LDAP server down (retry " + str(attempt) + "/" +
                    str(RETRY_COUNT) + ")")
            try:
                if not self.conn:
                    self.init_conn()
                result = self.conn.search_s(
                    query.base,
                    SCOPE_MAP[query.scope],
                    query.filter.replace("\\", "\\\\"),
                    query.attrs,
                )
                break
            except ldap.SERVER_DOWN:
                self.conn = None
                time.sleep(RETRY_DELAY)
        return result

    @property
    def url(self):
        return "ldap://" + self.host + ":" + str(self.port)

class LdapQuery(object):
    """
    Query referencing an LdapConnection and providing several
    methods for query manipulation.
    """

    name = "unknown"
    base = ""
    scope = "sub"
    filter = "(objectClass=*)"
    attrs = None
    connection = None
    result = None

    def __unicode__(self):
        return "LdapQuery:" + self.name

    def is_applicable(self, metadata):
        """
        Overrideable method to determine if the query is to be executed for
        the given metadata object.
        Defaults to true.
        """
        return True

    def prepare_query(self, metadata):
        """
        Overrideable method to alter the query based on metadata.
        Defaults to doing nothing.

        In most cases, you will do something like

            self.filter = "(cn=" + metadata.hostname + ")"

        here.
        """
        pass

    def process_result(self, metadata):
        """
        Overrideable method to post-process the query result.
        Defaults to returning the unaltered result.
        """
        return self.result

    def get_result(self, metadata):
        """
        Method to handle preparing, executing and processing the query.
        """
        if isinstance(self.connection, LdapConnection):
            self.prepare_query(metadata)
            self.result = self.connection.run_query(self)
            self.result = self.process_result(metadata)
            return self.result
        else:
            logger.error("LdapPlugin error: " +
              "No valid connection defined for query " + str(self))
            return None

class LdapSubQuery(LdapQuery):
    """
    SubQueries are meant for internal use only and are not added
    to the metadata object. They are useful for situations where
    you need to run more than one query to obtain some data.
    """
    def prepare_query(self, metadata, **kwargs):
        """
        Overrideable method to alter the query based on metadata.
        Defaults to doing nothing.
        """
        pass

    def process_result(self, metadata, **kwargs):
        """
        Overrideable method to post-process the query result.
        Defaults to returning the unaltered result.
        """
        return self.result

    def get_result(self, metadata, **kwargs):
        """
        Method to handle preparing, executing and processing the query.
        """
        if isinstance(self.connection, LdapConnection):
            self.prepare_query(metadata, **kwargs)
            self.result = self.connection.run_query(self)
            return self.process_result(metadata, **kwargs)
        else:
            logger.error("LdapPlugin error: " +
              "No valid connection defined for query " + str(self))
            return None
