#!/usr/bin/env python

import psyco
psyco.log()
psyco.profile(0.2)

from Core import Core
from sshbase import sshbase
from fstab import fstab
from myri import myri

gc=Core([sshbase,fstab,myri])

