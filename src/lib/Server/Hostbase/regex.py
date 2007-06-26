import re

date = re.compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
host = re.compile('^[a-z0-9-_]+(\.[a-z0-9-_]+)+$')
macaddr = re.compile('^[0-9abcdefABCDEF]{2}(:[0-9abcdefABCDEF]{2}){5}$|virtual')
ipaddr = re.compile('^[0-9]{1,3}(\.[0-9]{1,3}){3}$')
