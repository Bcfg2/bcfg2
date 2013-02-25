#!/usr/bin/python -Ott
""" Benchmark template rendering times """

import os
import sys
import time
import logging
import operator
import Bcfg2.Logger
import Bcfg2.Server.Core

LOGGER = None


def main():
    optinfo = \
        dict(client=Bcfg2.Options.Option("Benchmark templates for one client",
                                         cmd="--client",
                                         odesc="<client>",
                                         long_arg=True,
                                         default=None),
             )
    optinfo.update(Bcfg2.Options.CLI_COMMON_OPTIONS)
    optinfo.update(Bcfg2.Options.SERVER_COMMON_OPTIONS)
    setup = Bcfg2.Options.OptionParser(optinfo)
    setup.parse(sys.argv[1:])

    if setup['debug']:
        level = logging.DEBUG
    elif setup['verbose']:
        level = logging.INFO
    else:
        level = logging.WARNING
    Bcfg2.Logger.setup_logging("bcfg2-test",
                               to_console=setup['verbose'] or setup['debug'],
                               to_syslog=False,
                               to_file=setup['logging'],
                               level=level)
    logger = logging.getLogger(sys.argv[0])

    core = Bcfg2.Server.Core.BaseCore(setup)
    logger.info("Bcfg2 server core loaded")
    core.fam.handle_events_in_interval(0.1)
    logger.debug("Repository events processed")

    # how many times to render each template for each client
    runs = 5

    if setup['args']:
        templates = setup['args']
    else:
        templates = []

    if setup['client'] is None:
        clients = [core.build_metadata(c) for c in core.metadata.clients]
    else:
        clients = [core.build_metadata(setup['client'])]

    times = dict()
    for metadata in clients:
        for struct in core.GetStructures(metadata):
            logger.info("Rendering templates from structure %s:%s" %
                        (struct.tag, struct.get("name")))
            for entry in struct.xpath("//Path"):
                path = entry.get("name")
                logger.info("Rendering %s..." % path)
                times[path] = dict()
                avg = 0.0
                for i in range(runs):
                    start = time.time()
                    try:
                        core.Bind(entry, metadata)
                        avg += (time.time() - start) / runs
                    except:
                        break
                if avg:
                    logger.debug("   %s: %.02f sec" % (metadata.hostname, avg))
                    times[path][metadata.hostname] = avg

    # print out per-file results
    tmpltimes = []
    for tmpl, clients in times.items():
        try:
            avg = sum(clients.values()) / len(clients)
        except ZeroDivisionError:
            continue
        if avg > 0.01 or templates:
            tmpltimes.append((tmpl, avg))
    print("%-50s %s" % ("Template", "Average Render Time"))
    for tmpl, avg in reversed(sorted(tmpltimes, key=operator.itemgetter(1))):
        print("%-50s %.02f" % (tmpl, avg))

    # TODO: complain about templates that on average were quick but
    # for which some clients were slow


if __name__ == "__main__":
    sys.exit(main())
