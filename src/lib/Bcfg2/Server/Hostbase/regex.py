import re

date = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
host = re.compile(r'^[a-z0-9-_]+(\.[a-z0-9-_]+)+$')
macaddr = re.compile(r'^[0-9abcdefABCDEF]{2}(:[0-9abcdefABCDEF]{2}){5}$|virtual')
ipaddr = re.compile(r'^[0-9]{1,3}(\.[0-9]{1,3}){3}$')
