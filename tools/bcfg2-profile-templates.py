#!/usr/bin/python -Ott
# -*- coding: utf-8 -*-
""" Benchmark template rendering times """

import sys
import time
import math
import signal
import logging
import operator
import Bcfg2.Logger
import Bcfg2.Options
import Bcfg2.Server.Core


def stdev(nums):
    mean = float(sum(nums)) / len(nums)
    return math.sqrt(sum((n - mean)**2 for n in nums) / float(len(nums)))


def get_sigint_handler(core):
    """ Get a function that handles SIGINT/Ctrl-C by shutting down the
    core and exiting properly."""

    def hdlr(sig, frame):  # pylint: disable=W0613
        """ Handle SIGINT/Ctrl-C by shutting down the core and exiting
        properly. """
        core.shutdown()
        os._exit(1)  # pylint: disable=W0212

    return hdlr


def main():
    optinfo = dict(
        client=Bcfg2.Options.Option("Benchmark templates for one client",
                                    cmd="--client",
                                    odesc="<client>",
                                    long_arg=True,
                                    default=None),
        runs=Bcfg2.Options.Option("Number of rendering passes per template",
                                  cmd="--runs",
                                  odesc="<runs>",
                                  long_arg=True,
                                  default=5,
                                  cook=int))
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
    signal.signal(signal.SIGINT, get_sigint_handler(core))
    logger.info("Bcfg2 server core loaded")
    core.load_plugins()
    logger.debug("Plugins loaded")
    core.fam.handle_events_in_interval(0.1)
    logger.debug("Repository events processed")

    if setup['args']:
        templates = setup['args']
    else:
        templates = []

    if setup['client'] is None:
        clients = [core.build_metadata(c) for c in core.metadata.clients]
    else:
        clients = [core.build_metadata(setup['client'])]

    times = dict()
    client_count = 0
    for metadata in clients:
        client_count += 1
        logger.info("Rendering templates for client %s (%s/%s)" %
                    (metadata.hostname, client_count, len(clients)))
        structs = core.GetStructures(metadata)
        struct_count = 0
        for struct in structs:
            struct_count += 1
            logger.info("Rendering templates from structure %s:%s (%s/%s)" %
                        (struct.tag, struct.get("name"), struct_count,
                         len(structs)))
            entries = struct.xpath("//Path")
            entry_count = 0
            for entry in entries:
                entry_count += 1
                if templates and entry.get("name") not in templates:
                    continue
                logger.info("Rendering Path:%s (%s/%s)..." %
                            (entry.get("name"), entry_count, len(entries)))
                ptimes = times.setdefault(entry.get("name"), [])
                for i in range(setup['runs']):
                    start = time.time()
                    try:
                        core.Bind(entry, metadata)
                        ptimes.append(time.time() - start)
                    except:
                        break
                if ptimes:
                    avg = sum(ptimes) / len(ptimes)
                    if avg:
                        logger.debug("   %s: %.02f sec" %
                                     (metadata.hostname, avg))

    # print out per-file results
    tmpltimes = []
    for tmpl, ptimes in times.items():
        try:
            mean = float(sum(ptimes)) / len(ptimes)
        except ZeroDivisionError:
            continue
        ptimes.sort()
        median = ptimes[len(ptimes) / 2]
        std = stdev(ptimes)
        if mean > 0.01 or median > 0.01 or std > 1 or templates:
            tmpltimes.append((tmpl, mean, median, std))
    print("%-50s %-9s  %-11s  %6s" %
          ("Template", "Mean Time", "Median Time", "σ"))
    for info in reversed(sorted(tmpltimes, key=operator.itemgetter(1))):
        print("%-50s %9.02f  %11.02f  %6.02f" % info)
    core.shutdown()


if __name__ == "__main__":
    sys.exit(main())
