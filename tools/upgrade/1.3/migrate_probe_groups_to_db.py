#!/bin/env python
""" Migrate Probe host and group data from XML to DB backend for Metadata
and Probe plugins. Does not migrate individual probe return data. Assumes
migration to BOTH Metadata and Probe to database backends. """

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'Bcfg2.settings'

import lxml.etree
import sys
import Bcfg2.Options

from Bcfg2.Server.Plugins.Metadata import MetadataClientModel
from Bcfg2.Server.Plugins.Probes import ProbesGroupsModel

def migrate(xclient):
    """ Helper to do the migration given a <Client/> XML element """
    client_name = xclient.get('name')
    try:
        try:
            client = MetadataClientModel.objects.get(hostname=client_name)
        except MetadataClientModel.DoesNotExist:
            client = MetadataClientModel(hostname=client_name)
            client.save()
    except:
        print("Failed to migrate client %s" % (client))
        return False

    try:
        cgroups = []
        for xgroup in xclient.findall('Group'):
            group_name = xgroup.get('name')
            cgroups.append(group_name)
            try:
                group = ProbesGroupsModel.objects.get(hostname=client_name, group=group_name)
            except ProbesGroupsModel.DoesNotExist:
                group = ProbesGroupsModel(hostname=client_name, group=group_name)
                group.save()

        ProbesGroupsModel.objects.filter(
            hostname=client.hostname).exclude(
            group__in=cgroups).delete()

    except:
        print("Failed to migrate groups")
        return False
    return True

def main():
    """ Main """
    opts = dict(repo=Bcfg2.Options.SERVER_REPOSITORY)
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse(sys.argv[1:])

    probefile = os.path.join(setup['repo'], 'Probes', "probed.xml")

    try:
        xdata = lxml.etree.parse(probefile)
    except lxml.etree.XMLSyntaxError:
        err = sys.exc_info()[1]
        print("Could not parse %s, skipping: %s" % (probefile, err))
    
    for xclient in xdata.findall('Client'):
        print "Migrating Metadata and Probe groups for %s" % xclient.get('name')
        migrate(xclient)

if __name__ == '__main__':
    sys.exit(main())
