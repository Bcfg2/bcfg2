'''Bcfg2 logging support'''
__revision__ = '$Revision$'

import copy, fcntl, logging, logging.handlers, lxml.etree, math, struct, sys, termios, types

def print_attributes(attrib):
    ''' Add the attributes for an element'''
    return ' '.join(['%s="%s"' % data for data in attrib.iteritems()])

def print_text(text):
    ''' Add text to the output (which will need normalising '''
    charmap = {'<':'&lt;', '>':'&gt;', '&':'&amp;'}
    return ''.join([charmap.get(char, char) for char in text]) + '\n'
        
def xml_print(element, running_indent=0, indent=4):
    ''' Add an element and its children to the return string '''
    if (len(element.getchildren()) == 0) and (not element.text):
        ret = (' ' * running_indent)
        ret += '<%s %s/>\n' % (element.tag, print_attributes(element.attrib))
    else:
        child_indent = running_indent + indent
        ret = (' ' * running_indent)
        ret += '<%s%s>\n' % (element.tag, print_attributes(element))
        if element.text:                
            ret += (' '* child_indent) + print_text(element.text)
        for child in element.getchildren():
            ret += xml_print(child, child_indent, indent)
            ret += (' ' * running_indent) +  '</%s>\n' % (element.tag)
        if element.tail:
            ret += (' ' * child_indent) + print_text(element.tail)
    return ret

class TermiosFormatter(logging.Formatter):
    '''The termios formatter displays output in a terminal-sensitive fashion'''

    def __init__(self, fmt=None, datefmt=None):
        logging.Formatter.__init__(self, fmt, datefmt)
        if sys.stdout.isatty():
            # now get termios info
            try:
                self.width = struct.unpack('hhhh', fcntl.ioctl(0, termios.TIOCGWINSZ,
                                                               "\000"*8))[1]
                if self.width == 0:
                    self.width = 80
            except:
                self.width = 80
        else:
            # output to a pipe
            self.width = sys.maxint

    def format(self, record):
        '''format a record for display'''
        returns = []
        line_len = self.width
        if type(record.msg) in types.StringTypes:
            for line in record.msg.split('\n'):
                if len(line) <= line_len:
                    returns.append(line)
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
        elif type(record.msg) == lxml.etree._Element:
            returns.append(str(xml_print(record.msg)))
        else:
            returns.append("Got unsupported type %s" % (str(type(record.msg))))
            returns.append(record.name + ':' + str(record.msg))
        if record.exc_info:
            returns.append(self.formatException(record.exc_info))
        return '\n'.join(returns)

class FragmentingSysLogHandler(logging.handlers.SysLogHandler):
    '''This handler fragments messages into chunks smaller than 250 characters'''

    def __init__(self, procname, path, facility):
        self.procname = procname
        logging.handlers.SysLogHandler.__init__(self, path, facility)

    def emit(self, record):
        '''chunk and deliver records'''
        record.name = self.procname
        if str(record.msg) > 250:
            start = 0
            error = None
            if record.exc_info:
                error = record.exc_info
                record.exc_info = None
            msgdata = str(record.msg)
            while start < len(msgdata):
                newrec = copy.deepcopy(record)
                newrec.msg = msgdata[start:start+250]
                newrec.exc_info = error
                logging.handlers.SysLogHandler.emit(self, newrec)
                # only send the traceback once
                error = None
                start += 250
        else:
            logging.handlers.SysLogHandler.emit(self, newrec)
    
def setup_logging(procname, to_console=True, to_syslog=True, syslog_facility='local0', level=0):
    '''setup logging for bcfg2 software'''
    if hasattr(logging, 'already_setup'):
        return 
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    # tell the handler to use this format
    console.setFormatter(TermiosFormatter())
    syslog = FragmentingSysLogHandler(procname, '/dev/log', syslog_facility)
    syslog.setLevel(logging.DEBUG)
    syslog.setFormatter(logging.Formatter('%(name)s[%(process)d]: %(message)s'))
    # add the handler to the root logger
    if to_console:
        logging.root.addHandler(console)
    if to_syslog:
        logging.root.addHandler(syslog)
    logging.root.setLevel(level)
    logging.already_setup = True
