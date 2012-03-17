#!/usr/bin/python -Ott
""" Benchmark template rendering times """

import sys
import time
import logging
import logging.handlers
import operator
import lxml.etree
from Bcfg2.metargs import Option
import Bcfg2.Server.Core

LOGGER = None

def get_logger(args):
    """ set up logging according to the verbose level given on the
    command line """
    global LOGGER
    if LOGGER is None:
        LOGGER = logging.getLogger(sys.argv[0])
        stderr = logging.StreamHandler()
        level = logging.WARNING
        lformat = "%(message)s"
        if args.debug:
            stderr.setFormatter(logging.Formatter("%(asctime)s: %(levelname)s: %(message)s"))
            level = logging.DEBUG
        elif args.verbose:
            level = logging.INFO
        LOGGER.setLevel(level)
        LOGGER.addHandler(stderr)
        syslog = logging.handlers.SysLogHandler("/dev/log")
        syslog.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        LOGGER.addHandler(syslog)
    return LOGGER

def main():
    Bcfg2.Server.Core.Core.register_options()
    Bcfg2.Options.add_options(
        Option('--client', help="Benchmark templates for one client"),
        Option('templates', help="Templates to benchmark", nargs='*', metavar='template'),
        Bcfg2.Options.SERVER_REPOSITORY,
        Bcfg2.Options.DEBUG,
        Bcfg2.Options.VERBOSE,
    )
    args = Bcfg2.Options.args()
    logger = get_logger(args)

    core = Bcfg2.Server.Core.Core.from_config(args)
    logger.info("Bcfg2 server core loaded")
    core.fam.handle_events_in_interval(4)
    logger.debug("Repository events processed")

    # how many times to render each template for each client
    runs = 5

    templates = args.templates

    if args.client is None:
        clients = [core.build_metadata(c) for c in core.metadata.clients]
    else:
        clients = [core.build_metadata(args.client)]

    times = dict()
    for plugin in ['Cfg', 'TGenshi', 'TCheetah']:
        if plugin not in core.plugins:
            logger.debug("Skipping disabled plugin %s" % plugin)
            continue
        logger.info("Rendering templates from plugin %s" % plugin)

        entrysets = []
        for template in templates:
            try:
                entrysets.append(core.plugins[plugin].entries[template])
            except KeyError:
                logger.debug("Template %s not found in plugin %s" %
                             (template, plugin))
        if not entrysets:
            logger.debug("Using all entrysets in plugin %s" % plugin)
            entrysets = core.plugins[plugin].entries.values()

        for eset in entrysets:
            path = eset.path.replace(args.repository_path, '')
            logger.info("Rendering %s..." % path)
            times[path] = dict()
            for metadata in clients:
                avg = 0.0
                for i in range(runs):
                    entry = lxml.etree.Element("Path")
                    start = time.time()
                    try:
                        eset.bind_entry(entry, metadata)
                        avg += (time.time() - start) / runs
                    except:
                        break
                if avg:
                    logger.debug("   %s: %.02f sec" % (metadata.hostname, avg))
                    times[path][metadata.hostname] = avg

    # print out per-template results
    tmpltimes = []
    for tmpl, clients in times.items():
        try:
            avg = sum(clients.values()) / len(clients)
        except ZeroDivisionError:
            continue
        if avg > 0.01 or templates:
            tmpltimes.append((tmpl, avg))
    print "%-50s %s" % ("Template", "Average Render Time")
    for tmpl, avg in reversed(sorted(tmpltimes, key=operator.itemgetter(1))):
        print "%-50s %.02f" % (tmpl, avg)

    # TODO: complain about templates that on average were quick but
    # for which some clients were slow


if __name__ == "__main__":
    sys.exit(main())
