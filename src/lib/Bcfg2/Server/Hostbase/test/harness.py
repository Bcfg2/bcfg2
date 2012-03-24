import os, sys

here =  os.path.realpath('harness')

server_hostbase = os.path.realpath(here + '../../../../')

sys.path.insert(0,server_hostbase)
sys.path.insert(0,server_hostbase + '../')
#commented this out, but might be needed for now until the harness is figured out
#if so, use your actual path to the Hostbase module
#sys.path.insert(0,'/home/dahl/Code/bcfg2/src/lib/Server/Hostbase')
