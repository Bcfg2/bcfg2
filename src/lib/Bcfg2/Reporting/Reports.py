#!/usr/bin/env python
"""Query reporting system for client status."""

import sys
import argparse
import datetime
import Bcfg2.DBSettings


def hosts_by_entry_type(clients, etype, entryspec):
    result = []
    for entry in entryspec:
        for client in clients:
            items = getattr(client.current_interaction, etype)()
            for item in items:
                if (item.entry_type == entry[0] and
                    item.name == entry[1]):
                    result.append(client)
    return result


def print_fields(fields, client, fmt, extra=None):
    """ Prints the fields specified in fields of client, max_name
    specifies the column width of the name column. """
    fdata = []
    if extra is None:
        extra = dict()
    for field in fields:
        if field == 'time':
            fdata.append(str(client.current_interaction.timestamp))
        elif field == 'state':
            if client.current_interaction.isclean():
                fdata.append("clean")
            else:
                fdata.append("dirty")
        elif field == 'total':
            fdata.append(client.current_interaction.total_count)
        elif field == 'good':
            fdata.append(client.current_interaction.good_count)
        elif field == 'modified':
            fdata.append(client.current_interaction.modified_count)
        elif field == 'extra':
            fdata.append(client.current_interaction.extra_count)
        elif field == 'bad':
            fdata.append((client.current_interaction.bad_count))
        elif field == 'stale':
            fdata.append(client.current_interaction.isstale())
        else:
            try:
                fdata.append(getattr(client, field))
            except AttributeError:
                fdata.append(extra.get(field, "N/A"))

    print(fmt % tuple(fdata))


def print_entries(interaction, etype):
    items = getattr(interaction, etype)()
    for item in items:
        print("%-70s %s" % (item.entry_type + ":" + item.name, etype))


class _SingleHostCmd(Bcfg2.Options.Subcommand):  # pylint: disable=abstract-method
    """ Base class for bcfg2-reports modes that take a single host as
    a positional argument """
    options = [Bcfg2.Options.PositionalArgument("host")]

    def get_client(self, setup):
        from Bcfg2.Reporting.models import Client
        try:
            return Client.objects.select_related().get(name=setup.host)
        except Client.DoesNotExist:
            print("No such host: %s" % setup.host)
            raise SystemExit(2)


class Show(_SingleHostCmd):
    """ Show bad, extra, modified, or all entries from a given host """

    options = _SingleHostCmd.options + [
        Bcfg2.Options.BooleanOption(
            "-b", "--bad", help="Show bad entries from HOST"),
        Bcfg2.Options.BooleanOption(
            "-e", "--extra", help="Show extra entries from HOST"),
        Bcfg2.Options.BooleanOption(
            "-m", "--modified", help="Show modified entries from HOST")]

    def run(self, setup):
        client = self.get_client(setup)
        show_all = not setup.bad and not setup.extra and not setup.modified
        if setup.bad or show_all:
            print_entries(client.current_interaction, "bad")
        if setup.modified or show_all:
            print_entries(client.current_interaction, "modified")
        if setup.extra or show_all:
            print_entries(client.current_interaction, "extra")


class Total(_SingleHostCmd):
    """ Show total number of managed and good entries from HOST """

    def run(self, setup):
        client = self.get_client(setup)
        managed = client.current_interaction.total_count
        good = client.current_interaction.good_count
        print("Total managed entries: %d (good: %d)" % (managed, good))


class Expire(_SingleHostCmd):
    """ Toggle the expired/unexpired state of HOST """

    def run(self, setup):
        client = self.get_client(setup)
        if client.expiration is None:
            client.expiration = datetime.datetime.now()
            print("%s expired." % client.name)
        else:
            client.expiration = None
            print("%s un-expired." % client.name)
        client.save()


class _ClientSelectCmd(Bcfg2.Options.Subcommand):
    """ Base class for subcommands that display lists of clients """
    options = [
        Bcfg2.Options.Option("--fields", metavar="FIELD,FIELD,...",
                             help="Only display the listed fields",
                             type=Bcfg2.Options.Types.comma_list,
                             default=['name', 'time', 'state'])]

    def get_clients(self):
        from Bcfg2.Reporting.models import Client
        return Client.objects.exclude(current_interaction__isnull=True)

    def display(self, result, fields, extra=None):
        if 'name' not in fields:
            fields.insert(0, "name")
        if not result:
            print("No match found")
            return
        if extra is None:
            extra = dict()
        max_name = max(len(c.name) for c in result)
        ffmt = []
        for field in fields:
            if field == "name":
                ffmt.append("%%-%ds" % max_name)
            elif field == "time":
                ffmt.append("%-19s")
            else:
                ffmt.append("%%-%ds" % len(field))
        fmt = "  ".join(ffmt)
        print(fmt % tuple(f.title() for f in fields))
        for client in result:
            if not client.expiration:
                print_fields(fields, client, fmt,
                             extra=extra.get(client, None))


class Clients(_ClientSelectCmd):
    """ Query hosts """
    options = _ClientSelectCmd.options + [
        Bcfg2.Options.BooleanOption(
            "-c", "--clean", help="Show only clean hosts"),
        Bcfg2.Options.BooleanOption(
            "-d", "--dirty", help="Show only dirty hosts"),
        Bcfg2.Options.BooleanOption(
            "--stale",
            help="Show hosts that haven't run in the last 24 hours")]

    def run(self, setup):
        result = []
        show_all = not setup.stale and not setup.clean and not setup.dirty
        for client in self.get_clients():
            interaction = client.current_interaction
            if (show_all or
                (setup.stale and interaction.isstale()) or
                (setup.clean and interaction.isclean()) or
                (setup.dirty and not interaction.isclean())):
                result.append(client)

        self.display(result, setup.fields)


class Entries(_ClientSelectCmd):
    """ Query hosts by entries """
    options = _ClientSelectCmd.options + [
        Bcfg2.Options.BooleanOption(
            "--badentry",
            help="Show hosts that have bad entries that match"),
        Bcfg2.Options.BooleanOption(
            "--modifiedentry",
            help="Show hosts that have modified entries that match"),
        Bcfg2.Options.BooleanOption(
            "--extraentry",
            help="Show hosts that have extra entries that match"),
        Bcfg2.Options.PathOption(
            "--file", type=argparse.FileType('r'),
            help="Read TYPE:NAME pairs from the specified file instead of "
            "from the command line"),
        Bcfg2.Options.PositionalArgument(
            "entries", metavar="TYPE:NAME", nargs="*")]

    def run(self, setup):
        result = []
        if setup.file:
            try:
                entries = [l.strip().split(":") for l in setup.file]
            except IOError:
                err = sys.exc_info()[1]
                print("Cannot read entries from %s: %s" % (setup.file.name,
                                                           err))
                return 2
        else:
            entries = [a.split(":") for a in setup.entries]

        clients = self.get_clients()
        if setup.badentry:
            result = hosts_by_entry_type(clients, "bad", entries)
        elif setup.modifiedentry:
            result = hosts_by_entry_type(clients, "modified", entries)
        elif setup.extraentry:
            result = hosts_by_entry_type(clients, "extra", entries)

        self.display(result, setup.fields)


class Entry(_ClientSelectCmd):
    """ Show the status of a single entry on all hosts """

    options = _ClientSelectCmd.options + [
        Bcfg2.Options.PositionalArgument(
            "entry", metavar="TYPE:NAME", nargs=1)]

    def run(self, setup):
        from Bcfg2.Reporting.models import BaseEntry
        result = []
        fields = setup.fields
        if 'state' in fields:
            fields.remove('state')
        fields.append("entry state")

        etype, ename = setup.entry[0].split(":")
        try:
            entry_cls = BaseEntry.entry_from_type(etype)
        except ValueError:
            print("Unhandled/unknown type %s" % etype)
            return 2

        # TODO: batch fetch this.  sqlite could break
        extra = dict()
        for client in self.get_clients():
            ents = entry_cls.objects.filter(
                name=ename,
                interaction=client.current_interaction)
            if len(ents) == 0:
                continue
            extra[client] = {"entry state": ents[0].get_state_display(),
                             "reason": ents[0]}
            result.append(client)

        self.display(result, fields, extra=extra)


class CLI(Bcfg2.Options.CommandRegistry):
    """ CLI class for bcfg2-reports """

    def __init__(self):
        Bcfg2.Options.CommandRegistry.__init__(self)
        self.register_commands(globals().values())
        parser = Bcfg2.Options.get_parser(
            description="Query the Bcfg2 reporting subsystem",
            components=[self])
        parser.add_options(self.subcommand_options)
        parser.parse()

    def run(self):
        """ Run bcfg2-reports """
        return self.runcommand()
