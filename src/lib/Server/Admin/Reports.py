from Bcfg2.Server.Reports.reports.models import Client
from getopt import getopt
import datetime
import Bcfg2.Server.Admin

def timecompare(client1, client2):
    '''compares two clients by their timestamps'''
    return cmp(client1.current_interaction.timestamp, \
                   client2.current_interaction.timestamp)

def namecompare(client1, client2):
    '''compares two clients by their names'''
    return cmp(client1.name, client2.name)
    
def statecompare(client1, client2):
    '''compares two clients by their states'''
    clean1 = client1.current_interaction.isclean()
    clean2 = client2.current_interaction.isclean()

    if clean1 and not clean2:
        return -1
    elif clean2 and not clean1:
        return 1
    else:
        return 0

def crit_compare(criterion, client1, client2):
    '''compares two clients by the criteria provided in criterion'''
    for crit in criterion:
        comp = 0
        if crit == 'name':
            comp = namecompare(client1, client2)
        elif crit == 'state':
            comp = statecompare(client1, client2)
        elif crit == 'time':
            comp = timecompare(client1, client2)
        
        if comp != 0:
            return comp
    
    return 0

def print_fields(fields, cli, max_name):
    '''prints the fields specified in fields of cli, max_name specifies the column width of the name column'''
    display = ""
    if 'name' in fields:
        display += cli.name
        for i in range(len(cli.name), max_name):
            display += " "
    if 'time' in fields:
        display += "   "
        display += str(cli.current_interaction.timestamp)
    if 'state' in fields:
        display += "   "
        if cli.current_interaction.isclean():
            display += "clean"
        else:
            display += "dirty"
    print display

class Reports(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin reports'
    __longhelp__ = __shorthelp__ + '\n\t Command line interface for the reporting system'

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if "-h" in args:
            print "Usage: "
            print self.__shorthelp__
            raise SystemExit(1)
        
        fields = ""
        sort = ""
        badentry = ""
        expire = ""

        c_list = Client.objects.all()
        
        result = list()
        
        opts, pargs = getopt(args, 'cd', ['sort=', 'fields='])

        for option in opts:
            if len(option) > 0:
                if option[0] == '--fields':
                    fields = option[1]
                if option[0] == '--sort':
                    sort = option[1]
                if option[0] == '--badentry':
                    badentry = option[1]
                if option[0] == '-x':
                    expire = option[1]

        if expire != "":
            for c_inst in c_list:
                if expire == c_inst.name:
                    if c_inst.expiration == None:
                        c_inst.expiration = datetime.datetime.now()
                    else:
                        c_inst.expiration = None
                    c_inst.save()

        else:
            if fields == "":
                fields = ['name', 'time', 'state']
            else:
                fields = fields.split(',')

            if sort != "":
                sort = sort.split(',')

            if badentry != "":
                badentry = badentry.split(',')

            if '-c' in args:    
                for c_inst in c_list:
                    if c_inst.current_interaction.isclean():
                        result.append(c_inst)

            elif '-d' in args:    
                for c_inst in c_list:
                    if not c_inst.current_interaction.isclean():
                        result.append(c_inst)

            elif badentry != "":
                for c_inst in c_list:
                    baditems = c_inst.current_interaction.bad_items.all()
                    for item in baditems:
                        if item.name == badentry[1] and item.kind == badentry[0]:
                            result.append(c_inst)
                            break

            else:
                for c_inst in c_list:
                    result.append(c_inst)

            max_name = -1
            if 'name' in fields:
                for c_inst in result:
                    if len(c_inst.name) > max_name:
                        max_name = len(c_inst.name)

            if sort != "":
                result.sort(lambda x, y: crit_compare(sort, x, y))
    
            if fields != "":
                for c_inst in result:
                    print_fields(fields, c_inst, max_name)
