import re

__version__ = "1.3.0"

class Bcfg2VersionInfo(tuple):
    v_re = re.compile(r'(\d+)(\w+)(\d+)')

    def __new__(cls, vstr):
        (major, minor, rest) = vstr.split(".")
        match = cls.v_re.match(rest)
        if match:
            micro, releaselevel, serial = match.groups()
        else:
            micro = rest
            releaselevel = 'final'
            serial = 0
        return tuple.__new__(cls, [int(major), int(minor), int(micro),
                                   releaselevel, int(serial)])

    def __init__(self, vstr):
        tuple.__init__(self)
        self.major, self.minor, self.micro, self.releaselevel, self.serial = \
            tuple(self)
    
    def __repr__(self):
        return "(major=%s, minor=%s, micro=%s, releaselevel=%s, serial=%s)" % \
            tuple(self)

    def _release_cmp(self, r1, r2):
        if r1 == r2:
            return 0
        elif r1 == "final":
            return -1
        elif r2 == "final":
            return 1
        elif r1 == "rc":
            return -1
        elif r2 == "rc":
            return 1
            # should never get to anything past this point
        elif r1 == "pre":
            return -1
        elif r2 == "pre":
            return 1
        else:
            # wtf?
            return 0

    def __gt__(self, version):
        if version is None:
            # older bcfg2 clients didn't report their version, so we
            # handle this case specially and assume that any reported
            # version is newer than any indeterminate version
            return True
        try:
            for i in range(3):
                if self[i] > version[i]:
                    return True
                elif self[i] < version[i]:
                    return False
            rel = self._release_cmp(self[3], version[3])
            if rel < 0:
                return True
            elif rel > 0:
                return False
            if self[4] > version[4]:
                return True
            else:
                return False
        except TypeError:
            return self > Bcfg2VersionInfo(version)

    def __lt__(self, version):
        if version is None:
            # older bcfg2 clients didn't report their version, so we
            # handle this case specially and assume that any reported
            # version is newer than any indeterminate version
            return False
        try:
            for i in range(3):
                if self[i] < version[i]:
                    return True
                elif self[i] > version[i]:
                    return False
            rel = self._release_cmp(self[3], version[3])
            if rel > 0:
                return True
            elif rel < 0:
                return False
            if self[4] < version[4]:
                return True
            else:
                return False
        except TypeError:
            return self < Bcfg2VersionInfo(version)

    def __eq__(self, version):
        if version is None:
            # older bcfg2 clients didn't report their version, so we
            # handle this case specially and assume that any reported
            # version is newer than any indeterminate version
            return False
        try:
            rv = True
            for i in range(len(self)):
                rv &= self[i] == version[i]
            return rv
        except TypeError:
            return self == Bcfg2VersionInfo(version)

    def __ge__(self, version):
        return not self < version

    def __le__(self, version):
        return not self > version
