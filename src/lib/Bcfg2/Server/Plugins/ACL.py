""" Support for client ACLs based on IP address and client metadata """

import os
import struct
import socket
import Bcfg2.Server.Plugin


def rmi_names_equal(first, second):
    """ Compare two XML-RPC method names and see if they match.
    Resolves some limited wildcards; see
    :ref:`server-plugins-misc-acl-wildcards` for details.

    :param first: One of the ACLs to compare
    :type first: string
    :param second: The other ACL to compare
    :type second: string
    :returns: bool """
    if first == second:
        # single wildcard is special, and matches everything
        return True
    if first is None or second is None:
        return False
    if '*' not in first + second:
        # no wildcards, and not exactly equal
        return False
    first_parts = first.split('.')
    second_parts = second.split('.')
    if len(first_parts) != len(second_parts):
        return False
    for i in range(len(first_parts)):
        if (first_parts[i] != second_parts[i] and first_parts[i] != '*' and
                second_parts[i] != '*'):
            return False
    return True


def ip2int(ip):
    """ convert a dotted-quad IP address into an integer
    representation of the same """
    return struct.unpack('>L', socket.inet_pton(socket.AF_INET, ip))[0]


def ip_matches(ip, entry):
    """ Return True if the given IP matches the IP or IP and netmask
    in the given ACL entry; False otherwise """
    if entry.get("netmask"):
        try:
            mask = int("1" * int(entry.get("netmask")) +
                       "0" * (32 - int(entry.get("netmask"))), 2)
        except ValueError:
            mask = ip2int(entry.get("netmask"))
        return ip2int(ip) & mask == ip2int(entry.get("address")) & mask
    elif entry.get("address") is None:
        # no address, no netmask -- match all
        return True
    elif ip == entry.get("address"):
        # just a plain ip address
        return True
    return False


class IPACLFile(Bcfg2.Server.Plugin.XMLFileBacked):
    """ representation of ACL ip.xml, for IP-based ACLs """
    actions = dict(Allow=True,
                   Deny=False,
                   Defer=None)

    def check_acl(self, address, rmi):
        """ Check a client address against the ACL list """
        if not len(self.entries):
            # default defer if no ACLs are defined.
            self.debug_log("ACL: %s requests %s: No IP ACLs, defer" %
                           (address, rmi))
            return self.actions["Defer"]
        for entry in self.entries:
            if (ip_matches(address, entry) and
                    rmi_names_equal(entry.get("method"), rmi)):
                self.debug_log("ACL: %s requests %s: Found matching IP ACL, "
                               "%s" % (address, rmi, entry.tag.lower()))
                return self.actions[entry.tag]
        if address == "127.0.0.1":
            self.debug_log("ACL: %s requests %s: No matching IP ACLs, "
                           "localhost allowed" % (address, rmi))
            return self.actions['Allow']  # default allow for localhost

        self.debug_log("ACL: %s requests %s: No matching IP ACLs, defer" %
                       (address, rmi))
        return self.actions["Defer"]  # default defer for other machines


class MetadataACLFile(Bcfg2.Server.Plugin.StructFile):
    """ representation of ACL metadata.xml, for metadata-based ACLs """
    def check_acl(self, metadata, rmi):
        """ check client metadata against the ACL list """
        if not len(self.entries):
            # default allow if no ACLs are defined.
            self.debug_log("ACL: %s requests %s: No metadata ACLs, allow" %
                           (metadata.hostname, rmi))
            return True
        for el in self.Match(metadata):
            if rmi_names_equal(el.get("method"), rmi):
                self.debug_log("ACL: %s requests %s: Found matching metadata "
                               "ACL, %s" % (metadata.hostname, rmi,
                                            el.tag.lower()))
                return el.tag == "Allow"
        if metadata.hostname in ['localhost', 'localhost.localdomain']:
            # default allow for localhost
            self.debug_log("ACL: %s requests %s: No matching metadata ACLs, "
                           "localhost allowed" % (metadata.hostname, rmi))
            return True
        self.debug_log("ACL: %s requests %s: No matching metadata ACLs, deny" %
                       (metadata.hostname, rmi))
        return False  # default deny for other machines


class ACL(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.ClientACLs):
    """ allow connections to bcfg-server based on IP address """

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.ClientACLs.__init__(self)
        self.ip_acls = IPACLFile(os.path.join(self.data, 'ip.xml'),
                                 should_monitor=True)
        self.metadata_acls = MetadataACLFile(os.path.join(self.data,
                                                          'metadata.xml'),
                                             should_monitor=True)

    def check_acl_ip(self, address, rmi):
        self.debug_log("ACL: %s requests %s: Checking IP ACLs" %
                       (address[0], rmi))
        return self.ip_acls.check_acl(address[0], rmi)

    def check_acl_metadata(self, metadata, rmi):
        self.debug_log("ACL: %s requests %s: Checking metadata ACLs" %
                       (metadata.hostname, rmi))
        return self.metadata_acls.check_acl(metadata, rmi)

    def set_debug(self, debug):
        rv = Bcfg2.Server.Plugin.Plugin.set_debug(self, debug)
        self.ip_acls.set_debug(debug)
        self.metadata_acls.set_debug(debug)
        return rv
    set_debug.__doc__ = Bcfg2.Server.Plugin.Plugin.set_debug.__doc__
