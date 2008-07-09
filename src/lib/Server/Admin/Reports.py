import os, sys, binascii
try:
    import Bcfg2.Server.Reports.settings
except:
    sys.stderr.write("Failed to load configuration settings. is /etc/bcfg2.conf readable?")
    sys.exit(1)

project_directory = os.path.dirname(Bcfg2.Server.Reports.settings.__file__)
project_name = os.path.basename(project_directory)
sys.path.append(os.path.join(project_directory, '..'))
project_module = __import__(project_name, '', '', [''])
sys.path.pop()
# Set DJANGO_SETTINGS_MODULE appropriately.
os.environ['DJANGO_SETTINGS_MODULE'] = '%s.settings' % project_name

from Bcfg2.Server.Reports.reports.models import Client
import Bcfg2.Server.Admin

def timecompare(client1, client2):
    return cmp(client1.current_interaction.timestamp, \
                   client2.current_interaction.timestamp)

class Reports(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin reports'
    __longhelp__ = __shorthelp__ + '\n\t Command line interface for the reporting system'

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if "-h" in args:
            print "Usage: "
            print self.__shorthelp__
            raise SystemExit(1)

        c_list = Client.objects.all()
        
        result = list()
        
        if '-c' in args or '-d' in args:    
            for c_inst in c_list:
                if '-c' in args and c_inst.current_interaction.isclean() or \
                        '-d' in args and not \
                        c_inst.current_interaction.isclean():
                    result.append(c_inst)
        else:
            result = c_list
                    
        if '-s' in args:
            result.sort(timecompare)
                        
        for c_inst in result:
            print c_inst, c_inst.current_interaction.timestamp
    


