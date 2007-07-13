"""prngd module

This module interfaces with PRNGD - Pseudo Random Number Generator
Daemon for platforms without /dev/random or /dev/urandom.

It is based on code from Stuart D. Gathman stuart at bmsi.com and is
Public Domain. The original code is available from
http://mail.python.org/pipermail/python-list/2002-November/170737.html"""

import socket
from struct import unpack,pack

class PRNGD:
  "Provide access to the Portable Random Number Generator Daemon"

  def __init__(self,sockname="/var/run/egd-pool"):
    self.randfile = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    self.randfile.connect(sockname)

  def _readall(self,n):
    s = self.randfile.recv(n)
    while len(s) < n:
      s = s + self.randfile.recv(n - len(s))
    return s

  def get(self):
    "Return number of available bytes of entropy."
    self.randfile.sendall('\x00')
    return unpack(">i",self._readall(4))[0]

  def read(self,cnt):
    "Return available entropy, up to cnt bytes."
    if cnt > 255: cnt = 255
    self.randfile.sendall(pack("BB",0x01,cnt))
    buf = self._readall(1)
    assert len(buf) == 1
    count = unpack("B",buf)[0]
    buf = self._readall(count)
    assert len(buf) == count, "didn't get all the entropy"
    return buf

  def readall(self,cnt):
    "Return all entropy bytes requested"
    if cnt < 256:
      self.randfile.sendall(pack("BB",0x02,cnt))
      return self._readall(cnt)
    buf = readall(self,255)
    cnt -= len(buf)
    while cnt > 255:
      buf += readall(self,255)
      cnt -= len(buf)
    return buf + readall(self,cnt)

  def getpid(self):
    "Return the process id string of the prngd"
    self.randfile.sendall('\x04')
    buf = self._readall(1)
    assert len(buf) == 1
    count = unpack("B",buf)[0]
    buf = self._readall(count)
    assert len(buf) == count, "didn't get whole PID string"
    return buf
