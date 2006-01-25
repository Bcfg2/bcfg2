'''Bcfg2 logging support'''
__revision__ = '$Revision: $'

import copy, fcntl, logging, logging.handlers, math, struct, termios, types

class TermiosFormatter(logging.Formatter):
    '''The termios formatter displays output in a terminal-sensitive fashion'''

    def __init__(self, fmt=None, datefmt=None):
        logging.Formatter.__init__(self, fmt, datefmt)
        # now get termios info
        try:
            self.height, self.width = struct.unpack('hhhh',
                                                    fcntl.ioctl(0, termios.TIOCGWINSZ,
                                                                "\000"*8))[0:2]
            if self.height == 0 or self.width == 0:
                self.height, self.width = (25, 80)
        except:
            self.height, self.width = (25, 80)

    def format(self, record):
        '''format a record for display'''
        returns = []
        line_len = self.width - len(record.name) - 2
        if type(record.msg) in types.StringTypes:
            for line in record.msg.split('\n'):
                if len(line) <= line_len:
                    returns.append("%s: %s" % (record.name, line))
                else:
                    inner_lines = int(math.floor(float(len(line)) / line_len))+1
                    for i in xrange(inner_lines):
                        returns.append("%s: %s" % (record.name, line[i*line_len:(i+1)*line_len]))
        elif type(record.msg) == types.ListType:
            record.msg.sort()
            msgwidth = self.width - len(record.name) - 2
            columnWidth = max([len(item) for item in record.msg])
            columns = int(math.floor(float(msgwidth) / (columnWidth+2)))
            lines = int(math.ceil(float(len(record.msg)) / columns))
            for lineNumber in xrange(lines):
                indices = [idx for idx in [(colNum * lines) + lineNumber
                                           for colNum in range(columns)] if idx < len(record.msg)]
                format = record.name + ':' + (len(indices) * (" %%-%ds " % columnWidth))
                returns.append(format % tuple([record.msg[idx] for idx in indices]))
        else:
            # got unsupported type
            returns.append(record.name + ':' + str(record.msg))
        if record.exc_info:
            returns.append(self.formatException(record.exc_info))
        return '\n'.join(returns)

class FragmentingSysLogHandler(logging.handlers.SysLogHandler):
    '''This handler fragments messages into chunks smaller than 250 characters'''

    def emit(self, record):
        '''chunk and deliver records'''
        if str(record.msg) > 250:
            start = 0
            msgdata = str(record.msg)
            while start < len(msgdata):
                newrec = copy.deepcopy(record)
                newrec.msg = msgdata[start:start+250]
                logging.handlers.SysLogHandler.emit(self, newrec)
                start += 250
        else:
            logging.handlers.SysLogHandler.emit(self, newrec)
    
def setup_logging(to_console=True, to_syslog=True, level=0):
    '''setup logging for bcfg2 software'''
    if hasattr(logging, 'enabled'):
        return 
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    # tell the handler to use this format
    console.setFormatter(TermiosFormatter())
    syslog = FragmentingSysLogHandler('/dev/log', 'local0')
    syslog.setLevel(logging.DEBUG)
    syslog.setFormatter(logging.Formatter('%(name)s[%(process)d]: %(message)s'))
    # add the handler to the root logger
    if to_console:
        logging.root.addHandler(console)
    if to_syslog:
        logging.root.addHandler(syslog)
    logging.root.level = level
    logging.enabled = True


        
