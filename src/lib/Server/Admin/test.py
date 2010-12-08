import os
import time
import tarfile
import sys
datastore = '/var/lib/bcfg2'

#Popen(['git', 'clone', 'https://github.com/solj/bcfg2-repo.git', datastore])
#timestamp = time.strftime('%Y%m%d%H%M%S')
#format = 'gz'
#mode = 'w:' + format
#filename = timestamp + '.tar' + '.' + format
#out = tarfile.open('/home/fab/' + filename, mode=mode)


#content = os.listdir(os.getcwd())           
#for item in content:
#    out.add(item)
#out.close()
#print "Archive %s was stored.\nLocation: %s" % (filename, datastore) 

#print os.getcwd()
#print os.listdir(os.getcwd())

#import shlex
#args = shlex.split('env LC_ALL=C git clone https://github.com/solj/bcfg2-repo.git datastore')
#print args

#Popen("env LC_ALL=C git clone https://github.com/solj/bcfg2-repo.git datastore")

#timestamp = time.strftime('%Y%m%d%H%M%S')
#format = 'gz'
#mode = 'w:' + format
#filename = timestamp + '.tar' + '.' + format
#out = tarfile.open(name = filename, mode = mode)
##content = os.listdir(datastore)    
##for item in content:
##    out.add(item)
##out.close()

###t = tarfile.open(name = destination, mode = 'w:gz')
#out.add(datastore, os.path.basename(datastore))
#out.close()

#print datastore, os.path.basename(datastore)

#content = os.listdir(datastore)    
#for item in content:
#    #out.add(item)
#    print item

#timestamp = time.strftime('%Y%m%d%H%M%S')
#format = 'gz'
#mode = 'w:' + format
#filename = timestamp + '.tar' + '.' + format

if len(sys.argv) == 0:
    destination = datastore + '/'
else:
    destination = sys.argv[1]

print destination
#out = tarfile.open(destination + filename, mode=mode)
#out.add(self.datastore, os.path.basename(self.datastore))
#out.close()
#print "Archive %s was stored at %s" % (filename, destination)

#print 'Die Kommandozeilenparameter sind:'
##for i in sys.argv:
##	print i

#print sys.argv[0]
#print sys.argv[1]
##print sys.argv[2]
