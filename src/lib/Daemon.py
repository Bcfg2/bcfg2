'''Bcfg2 daemon support'''
__revision__ = '$Revision$'

import os
import sys

def daemonize(filename):
    '''Do the double fork/setsession dance'''
    # Check if the pid is active
    try:
        pidfile = open(filename, "r")
        oldpid = int(pidfile.readline())
        # getpgid() will retun an IO error if all fails
        os.getpgid(oldpid)
        pidfile.close()

        # If we got this far without exceptions, there is another instance
        # running. Exit gracefully.
        print("PID File (%s) exists and listed PID (%d) is active." % \
              (filename, oldpid))
        raise SystemExit(1)
    except OSError:
        pidfile.close()
    except (IOError, ValueError): 
        # pid file doesn't
        pass

    # Fork once
    if os.fork() != 0:      
        os._exit(0)         
    os.setsid()                     # Create new session
    pid = os.fork()
    if pid != 0:
        try:
            pidfile = open(filename, "w")
            pidfile.write("%i" % pid)
            pidfile.close()
        except:
            print("Failed to write pid file %s" % filename)
        os._exit(0)     
    os.chdir("/")         
    os.umask(0)

    null = open("/dev/null", "w+")

    os.dup2(null.fileno(), sys.__stdin__.fileno())
    os.dup2(null.fileno(), sys.__stdout__.fileno())
    os.dup2(null.fileno(), sys.__stderr__.fileno())
