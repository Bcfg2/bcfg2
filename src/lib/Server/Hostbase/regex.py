import re

date = re.compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
host = re.compile('^[a-z0-9-_]+(\.[a-z0-9-_]+)+$')
printq = re.compile('^[a-z0-9-]+$')
user = re.compile('^[a-z0-9-_\.@]+$')
location = re.compile('^[0-9]{3}-[a-zA-Z][0-9]{3}$|none|bmr|cave|dsl|evl|mobile|offsite|mural|activespaces')
macaddr = re.compile('^[0-9abcdef]{2}(:[0-9abcdef]{2}){5}$|virtual')
ipaddr = re.compile('^[0-9]{1,3}(\.[0-9]{1,3}){3}$')
