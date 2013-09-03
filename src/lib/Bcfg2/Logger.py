"""Bcfg2 logging support"""

import copy
import fcntl
import logging
import logging.handlers
import math
import socket
import struct
import sys
import termios
import Bcfg2.Options

logging.raiseExceptions = 0


class TermiosFormatter(logging.Formatter):
    """The termios formatter displays output
    in a terminal-sensitive fashion.
    """

    def __init__(self, fmt=None, datefmt=None):
        logging.Formatter.__init__(self, fmt, datefmt)
        if sys.stdout.isatty():
            # now get termios info
            try:
                self.width = struct.unpack('hhhh',
                                           fcntl.ioctl(0,
                                                       termios.TIOCGWINSZ,
                                                       "\000" * 8))[1]
                if self.width == 0:
                    self.width = 80
            except:  # pylint: disable=W0702
                self.width = 80
        else:
            # output to a pipe
            self.width = 32768

    def format(self, record):
        '''format a record for display'''
        returns = []
        line_len = self.width
        if isinstance(record.msg, str):
            for line in record.msg.split('\n'):
                if len(line) <= line_len:
                    returns.append(line)
                else:
                    inner_lines = \
                        int(math.floor(float(len(line)) / line_len)) + 1
                    for msgline in range(inner_lines):
                        returns.append(
                            line[msgline * line_len:(msgline + 1) * line_len])
        elif isinstance(record.msg, list):
            if not record.msg:
                return ''
            record.msg.sort()
            msgwidth = self.width
            col_width = max([len(item) for item in record.msg])
            columns = int(math.floor(float(msgwidth) / (col_width + 2)))
            lines = int(math.ceil(float(len(record.msg)) / columns))
            for lineno in range(lines):
                indices = [idx for idx in [(colNum * lines) + lineno
                                           for colNum in range(columns)]
                           if idx < len(record.msg)]
                retformat = (len(indices) * (" %%-%ds " % col_width))
                returns.append(retformat % tuple([record.msg[idx]
                                                  for idx in indices]))
        else:
            returns.append(str(record.msg))
        if record.exc_info:
            returns.append(self.formatException(record.exc_info))
        return '\n'.join(returns)


class FragmentingSysLogHandler(logging.handlers.SysLogHandler):
    """
       This handler fragments messages into
       chunks smaller than 250 characters
    """

    def __init__(self, procname, path, facility):
        self.procname = procname
        self.unixsocket = False
        logging.handlers.SysLogHandler.__init__(self, path, facility)

    def emit(self, record):
        """Chunk and deliver records."""
        record.name = self.procname
        if isinstance(record.msg, str):
            msgs = []
            error = record.exc_info
            record.exc_info = None
            msgdata = record.msg
            if len(msgdata) == 0:
                return
            while msgdata:
                newrec = copy.copy(record)
                newrec.msg = msgdata[:250]
                msgs.append(newrec)
                msgdata = msgdata[250:]
            msgs[0].exc_info = error
        else:
            msgs = [record]
        for newrec in msgs:
            msg = '<%d>%s\000' % \
                (self.encodePriority(self.facility, newrec.levelname.lower()),
                 self.format(newrec))
            try:
                try:
                    encoded = msg.encode('utf-8')
                except UnicodeDecodeError:
                    encoded = msg
                self.socket.send(encoded)
            except socket.error:
                for i in range(10):  # pylint: disable=W0612
                    try:
                        if isinstance(self.address, tuple):
                            self.socket = socket.socket(socket.AF_INET,
                                                        socket.SOCK_DGRAM)
                            self.socket.connect(self.address)
                        else:
                            self._connect_unixsocket(self.address)
                        break
                    except socket.error:
                        continue
                try:
                    reconn = copy.copy(record)
                    reconn.msg = 'Reconnected to syslog'
                    self.socket.send('<%d>%s\000' %
                                     (self.encodePriority(self.facility,
                                                          logging.WARNING),
                                      self.format(reconn)))
                    self.socket.send(msg)
                except:  # pylint: disable=W0702
                    # If we still fail then drop it.  Running
                    # bcfg2-server as non-root can trigger permission
                    # denied exceptions.
                    pass


def add_console_handler(level=logging.DEBUG):
    """ Add a logging handler that logs at a level to sys.stderr """
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    # tell the handler to use this format
    console.setFormatter(TermiosFormatter())
    try:
        console.set_name("console")  # pylint: disable=E1101
    except AttributeError:
        console.name = "console"  # pylint: disable=W0201
    logging.root.addHandler(console)


def add_syslog_handler(procname=None, syslog_facility='daemon',
                       level=logging.DEBUG):
    """Add a logging handler that logs as procname to syslog_facility."""
    if procname is None:
        procname = Bcfg2.Options.get_parser().prog
    try:
        try:
            syslog = FragmentingSysLogHandler(procname,
                                              '/dev/log',
                                              syslog_facility)
        except socket.error:
            syslog = FragmentingSysLogHandler(procname,
                                              ('localhost', 514),
                                              syslog_facility)
        try:
            syslog.set_name("syslog")  # pylint: disable=E1101
        except AttributeError:
            syslog.name = "syslog"  # pylint: disable=W0201
        syslog.setLevel(level)
        syslog.setFormatter(
            logging.Formatter('%(name)s[%(process)d]: %(message)s'))
        logging.root.addHandler(syslog)
    except socket.error:
        logging.root.error("Failed to activate syslogging")
    except:
        print("Failed to activate syslogging")


def add_file_handler(level=logging.DEBUG):
    """Add a logging handler that logs to a file."""
    filelog = logging.FileHandler(Bcfg2.Options.setup.logfile)
    try:
        filelog.set_name("file")  # pylint: disable=E1101
    except AttributeError:
        filelog.name = "file"  # pylint: disable=W0201
    filelog.setLevel(level)
    filelog.setFormatter(
        logging.Formatter('%(asctime)s %(name)s[%(process)d]: %(message)s'))
    logging.root.addHandler(filelog)


def default_log_level():
    """ Get the default log level, according to the configuration """
    if Bcfg2.Options.setup.debug:
        return logging.DEBUG
    elif Bcfg2.Options.setup.verbose:
        return logging.INFO
    else:
        return logging.WARNING


def setup_logging():
    """Setup logging for Bcfg2 software."""
    if hasattr(logging, 'already_setup'):
        return

    level = default_log_level()
    params = []

    to_console = True
    if hasattr(Bcfg2.Options.setup, "daemon"):
        if Bcfg2.Options.setup.daemon:
            to_console = False
        # if a command can be daemonized, but hasn't been, then we
        # assume that they're running it in the foreground and thus
        # want some more output.
        clvl = min(level, logging.INFO)
    else:
        clvl = level
    if to_console:
        params.append("%s to console" % logging.getLevelName(clvl))
        add_console_handler(level=clvl)

    if hasattr(Bcfg2.Options.setup, "syslog") and Bcfg2.Options.setup.syslog:
        slvl = min(level, logging.INFO)
        params.append("%s to syslog" % logging.getLevelName(slvl))
        add_syslog_handler(level=slvl)

    if Bcfg2.Options.setup.logfile:
        params.append("%s to %s" % (logging.getLevelName(level),
                                    Bcfg2.Options.setup.logfile))
        add_file_handler(level=level)

    logging.root.setLevel(logging.DEBUG)
    logging.root.debug("Configured logging: %s" % "; ".join(params))
    logging.already_setup = True


class Debuggable(object):
    """ Mixin to add a debugging interface to an object """

    options = []

    #: List of names of methods to be exposed as XML-RPC functions, if
    #: applicable to the child class
    __rmi__ = ['toggle_debug', 'set_debug']

    #: How exposed XML-RPC functions should be dispatched to child
    #: processes.
    __child_rmi__ = __rmi__[:]

    def __init__(self, name=None):
        """
        :param name: The name of the logger object to get.  If none is
                     supplied, the full name of the class (including
                     module) will be used.
        :type name: string
        """
        if name is None:
            name = "%s.%s" % (self.__class__.__module__,
                              self.__class__.__name__)
        self.debug_flag = Bcfg2.Options.setup.debug
        self.logger = logging.getLogger(name)

    def set_debug(self, debug):
        """ Explicitly enable or disable debugging.

        :returns: bool - The new value of the debug flag
        """
        self.debug_flag = debug
        return debug

    def toggle_debug(self):
        """ Turn debugging output on or off.

        :returns: bool - The new value of the debug flag
        """
        return self.set_debug(not self.debug_flag)

    def debug_log(self, message, flag=None):
        """ Log a message at the debug level.

        :param message: The message to log
        :type message: string
        :param flag: Override the current debug flag with this value
        :type flag: bool
        :returns: None
        """
        if (flag is None and self.debug_flag) or flag:
            self.logger.error(message)


class _OptionContainer(object):
    """ Container for options loaded at import-time to configure
    logging """
    options = [
        Bcfg2.Options.BooleanOption(
            '-d', '--debug', help='Enable debugging output',
            cf=('logging', 'debug')),
        Bcfg2.Options.BooleanOption(
            '-v', '--verbose', help='Enable verbose output',
            cf=('logging', 'verbose')),
        Bcfg2.Options.PathOption(
            '-o', '--logfile', help='Set path of file log',
            cf=('logging', 'path'))]

    @staticmethod
    def options_parsed_hook():
        """ initialize settings from /etc/bcfg2-web.conf or
        /etc/bcfg2.conf, or set up basic defaults.  this lets
        manage.py work in all cases """
        setup_logging()


Bcfg2.Options.get_parser().add_component(_OptionContainer)
