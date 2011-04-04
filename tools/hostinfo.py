#!/usr/bin/python
"""Hostinfo queries the hostbase database according to user-defined data"""

from os import system, environ
environ['DJANGO_SETTINGS_MODULE'] = 'Hostbase.settings'
from getopt import gnu_getopt, GetoptError
from django.db import connection
import sys

logic_ops = ["and", "or"]
host_attribs = ["hostname", "whatami", "netgroup", "security_class",
                "support", "csi", "memory", "printq", "dhcp", "outbound_smtp",
                "primary_user", "administrator", "location",
                "comments", "last", "expiration_date"]
dispatch = {'mac_addr': ' i.',
            'hdwr_type': ' i.',
            'ip_addr': ' p.',
            'name': ' n.',
            'dns_view': ' n.',
            'cname': ' c.',
            'mx': ' m.',
            'priority': ' m.'}


def pinger(hosts):
    """Function that uses fping to ping multiple hosts in parallel"""
    hostnames = ""
    for each in hosts:
        hostnames += each[0] + " "
    system("fping -r 1" + hostnames)
    sys.exit()


def get_query(arguments):
    """Parses the command line options and returns the necessary
    data for an SQL query"""
    logic = None
    resultset = []
    querystring = ''
    while 1:
        notflag = False
        if arguments[0] == 'not':
            notflag = True
            querypos = 1
        elif arguments[0] in logic_ops:
            logic = arguments[0]
            if arguments[1] == 'not':
                notflag = True
                querypos = 2
            else:
                querypos = 1
        else:
            querypos = 0
        if len(arguments[querypos].split("==")) > 1:
            operator = "="
            if notflag:
                operator = "<>"
            querysplit = arguments[querypos].split("==")
            if querysplit[0] in host_attribs:
                querystring = " h.%s%s\'%s\'" % (querysplit[0],
                                                 operator,
                                                 querysplit[1])
            elif querysplit[0] in dispatch:
                querystring = dispatch[querysplit[0]]
                querystring += "%s%s\'%s\'" % (querysplit[0],
                                               operator,
                                               querysplit[1])
        elif len(arguments[querypos].split("=")) > 1:
            notstring = ''
            if notflag:
                notstring = 'NOT '
            querysplit = arguments[querypos].split("=")
            if querysplit[0] in host_attribs:
                querystring = " h.%s %sLIKE \'%%%%%s%%%%\'" % (querysplit[0],
                                                               notstring,
                                                               querysplit[1])
            elif querysplit[0] in dispatch:
                querystring = dispatch[querysplit[0]]
                querystring += "%s %sLIKE \'%%%%%s%%%%\'" % (querysplit[0],
                                                             notstring,
                                                             querysplit[1])
        else:
            print("ERROR: bad query format")
            sys.exit()
        if not querystring:
            print("ERROR: bad query format")
            sys.exit()
        resultset.append((querystring, logic))
        arguments = arguments[querypos + 1:]
        if arguments == [] or arguments[0] not in logic_ops:
            break
    return resultset

try:
    (opts, args) = gnu_getopt(sys.argv[1:],
                             'q:', ['showfields', 'fields', 'ping', 'summary'])
    cursor = connection.cursor()
    if ('--showfields', '') in opts:
        print("\nhost fields:\n")
        for field in host_attribs:
            print(field)
        for field in dispatch:
            print(field)
        print("")
        sys.exit()
    if opts[0][0] == '-q':
        results = get_query(sys.argv[2:])
        queryoptions = ""
        for result in results:
            if result[1] == 'and':
                queryoptions += " AND " + result[0]
            elif result[1] == 'or':
                queryoptions += " OR " + result[0]
            else:
                queryoptions += result[0]
    if ('--summary', '') in opts:
        fields = "h.hostname, h.whatami, h.location, h.primary_user"
        query = """SELECT DISTINCT %s FROM (((((hostbase_host h
        INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id)
        INNER JOIN hostbase_name n ON p.id = n.ip_id)
        INNER JOIN hostbase_name_mxs x ON x.name_id = n.id)
        INNER JOIN hostbase_mx m ON m.id = x.mx_id)
        LEFT JOIN hostbase_cname c ON n.id = c.name_id
        WHERE %s ORDER BY h.hostname
        """ % (fields, queryoptions)
        cursor.execute(query)
        results = cursor.fetchall()
        if not results:
            print("No matches were found for your query")
            sys.exit()
        print("\n%-32s %-10s %-10s %-10s" % ('Hostname', 'Type', 'Location', 'User'))
        print("================================ ========== ========== ==========")
        for host in results:
            print("%-32s %-10s %-10s %-10s" % (host))
        print("")
    elif ('--fields', '') in opts:
        tolook = [arg for arg in args if arg in host_attribs or arg in dispatch]
        fields = ""
        fields = ", ".join(tolook)
        if not fields:
            print("No valid fields were entered.  exiting...")
            sys.exit()
        query = """SELECT DISTINCT %s FROM (((((hostbase_host h
        INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id)
        INNER JOIN hostbase_name n ON p.id = n.ip_id)
        INNER JOIN hostbase_name_mxs x ON x.name_id = n.id)
        INNER JOIN hostbase_mx m ON m.id = x.mx_id)
        LEFT JOIN hostbase_cname c ON n.id = c.name_id
        WHERE %s ORDER BY h.hostname
        """ % (fields, queryoptions)

        cursor.execute(query)
        results = cursor.fetchall()

        last = results[0]
        for field in results[0]:
            print(repr(field) + "\t")
        for host in results:
            if not host == last:
                for field in host:
                    print(repr(field) + "\t")
            last = host
            print("")
    else:
        basequery = """SELECT DISTINCT h.hostname FROM (((((hostbase_host h
        INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id)
        INNER JOIN hostbase_name n ON p.id = n.ip_id)
        INNER JOIN hostbase_name_mxs x ON x.name_id = n.id)
        INNER JOIN hostbase_mx m ON m.id = x.mx_id)
        LEFT JOIN hostbase_cname c ON n.id = c.name_id
        WHERE
        """
        cursor.execute(basequery + queryoptions + " ORDER BY h.hostname")
        results = cursor.fetchall()

        if not results:
            print("No matches were found for your query")
            sys.exit()

        if ("--ping", '') in opts:
            pinger(results)

        for host in results:
            print(host[0])


except (GetoptError, IndexError):
    print("\nUsage: hostinfo.py -q <field>=[=]<value> [and/or <field>=<value> [--long option]]")
    print("       hostinfo.py --showfields\tshows all data fields")
    print("\n    long options:")
    print("\t --fields f1 f2 ...\tspecifies the fields displayed from the queried hosts")
    print("\t --summary\t\tprints out a predetermined set of fields")
    print("\t --ping\t\t\tuses fping to ping all queried hosts\n")
    sys.exit()
