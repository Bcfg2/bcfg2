"""Bcfg2 logging support"""
__revision__ = '$Revision$'

import copy
import fcntl
import logging
import logging.handlers
import math
import socket
import struct
import sys
import termios

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
            except:
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
                    inner_lines = int(math.floor(float(len(line)) / line_len)) + 1
                    for i in range(inner_lines):
                        returns.append("%s" % (line[i * line_len:(i + 1) * line_len]))
        elif isinstance(record.msg, list):
            if not record.msg:
                return ''
            record.msg.sort()
            msgwidth = self.width
            columnWidth = max([len(item) for item in record.msg])
            columns = int(math.floor(float(msgwidth) / (columnWidth + 2)))
            lines = int(math.ceil(float(len(record.msg)) / columns))
            for lineNumber in range(lines):
                indices = [idx for idx in [(colNum * lines) + lineNumber
                                           for colNum in range(columns)] if idx < len(record.msg)]
                format = (len(indices) * (" %%-%ds " % columnWidth))
                returns.append(format % tuple([record.msg[idx] for idx in indices]))
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
            while msgdata:
                newrec = copy.deepcopy(record)
                newrec.msg = msgdata[:250]
                msgs.append(newrec)
                msgdata = msgdata[250:]
            msgs[0].exc_info = error
        else:
            msgs = [record]
        for newrec in msgs:
            msg = self.log_format_string % (self.encodePriority(self.facility,
                                                                newrec.levelname.lower()),
                                            self.format(newrec))
            try:
                self.socket.send(msg.encode('ascii'))
            except socket.error:
                for i in range(10):
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
                    self.socket.send("Reconnected to syslog")
                    self.socket.send(msg)
                except:
                    """
                    If we still fail then drop it.  Running bcfg2-server as non-root can
                    trigger permission denied exceptions.
                    """
                    pass


def add_console_handler(level):
    """Add a logging handler that logs at a level to sys.stdout."""
    console = logging.StreamHandler(sys.stdout)
    if level is True:
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(level)
    # tell the handler to use this format
    console.setFormatter(TermiosFormatter())
    logging.root.addHandler(console)


def add_syslog_handler(procname, syslog_facility):
    """Add a logging handler that logs as procname to syslog_facility."""
    try:
        try:
            syslog = FragmentingSysLogHandler(procname,
                                              '/dev/log',
                                              syslog_facility)
        except socket.error:
            syslog = FragmentingSysLogHandler(procname,
                                              ('localhost', 514),
                                              syslog_facility)
        syslog.setLevel(logging.DEBUG)
        syslog.setFormatter(logging.Formatter('%(name)s[%(process)d]: %(message)s'))
        logging.root.addHandler(syslog)
    except socket.error:
        logging.root.error("failed to activate syslogging")
    except:
        print("Failed to activate syslogging")


def add_file_handler(to_file):
    """Add a logging handler that logs to to_file."""
    filelog = logging.FileHandler(to_file)
    filelog.setLevel(logging.DEBUG)
    filelog.setFormatter(logging.Formatter('%(asctime)s %(name)s[%(process)d]: %(message)s'))
    logging.root.addHandler(filelog)


def setup_logging(procname, to_console=True, to_syslog=True,
                  syslog_facility='daemon', level=0, to_file=None):
    """Setup logging for Bcfg2 software."""
    if hasattr(logging, 'already_setup'):
        return

    if to_console:
        add_console_handler(to_console)
    if to_syslog:
        add_syslog_handler(procname, syslog_facility)
    if to_file is not None:
        add_file_handler(to_file)

    logging.root.setLevel(level)
    logging.already_setup = True
