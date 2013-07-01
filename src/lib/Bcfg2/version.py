""" bcfg2 version declaration and handling """

import re

__version__ = "1.3.2"


class Bcfg2VersionInfo(tuple):  # pylint: disable=E0012,R0924
    """ object to make granular version operations (particularly
    comparisons) easier """

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

    def __init__(self, vstr):  # pylint: disable=W0613
        tuple.__init__(self)
        self.major, self.minor, self.micro, self.releaselevel, self.serial = \
            tuple(self)

    def __repr__(self):
        return "%s(major=%s, minor=%s, micro=%s, releaselevel=%s, serial=%s)" \
            % ((self.__class__.__name__,) + tuple(self))

    def _release_cmp(self, rel1, rel2):  # pylint: disable=R0911
        """ compare two release numbers """
        if rel1 == rel2:
            return 0
        elif rel1 == "final":
            return -1
        elif rel2 == "final":
            return 1
        elif rel1 == "rc":
            return -1
        elif rel2 == "rc":
            return 1
            # should never get to anything past this point
        elif rel1 == "pre":
            return -1
        elif rel2 == "pre":
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
                if self[i] != version[i]:
                    return self[i] > version[i]
            rel = self._release_cmp(self[3], version[3])
            if rel != 0:
                return rel < 0
            return self[4] > version[4]
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
                if self[i] != version[i]:
                    return self[i] < version[i]
            rel = self._release_cmp(self[3], version[3])
            if rel != 0:
                return rel > 0
            return self[4] < version[4]
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
