#!/usr/bin/python -O
""" Send email about Bcfg2 commits from an SVN postcommit hook

This script can be used to send email from a Subversion postcommit
hook.  It emails out a list of diffs, with a few exceptions:

* If a file was deleted, the deletion is noted but no diff is included
* If the file matches a set of blacklist patterns (configurable; by
  default: /Ohai/*.json, */Probes/probed.xml, */SSHbase/*,
  */Packages/packages.conf), then the diff is not included but the file
  is listed as 'sensitive.'  (This is a bit of a broad brush, since the
  stuff in Probes and Ohai isn't necessarily sensitive, just annoying to
  get diffs for.)
* If the file is a directory, not a file, it is omitted
* If he file is binary, that is noted instead of a diff being included
* If the diff exceeds 100 lines (configurable), then a 'large diff' is
  mentioned, but not included.
* If the file is a Property file and is flagged as sensitive in the
  opening Property tag, then it is listed as sensitive and no diff is
  included.
* If the file is flagged as sensitive in its info.xml, then it is
  listed as sensitive and no diff is included.

The script attempts to look up the committing user's email address in
LDAP; it uses the system LDAP config to do so.  Currently it looks in
/etc/ldap.conf, /etc/openldap/ldap.conf, and /etc/nss_ldap.conf to
figure out the LDAP config, so it doesn't work with SSSD or with OSes
that keep their LDAP configs in other places.

The config file, /etc/bcfg2_svnlog.conf, should contain one stanza per
repository.  (If you just have one Bcfg2 repo, then you only need one
stanza.  This script unfortunately does not support different
configurations for different branches.)  Each stanza should look like this:

[<repo name>]
email=<address to email on commit>
subject=<tag to prepend to the Subject line>
largediff=<# of lines a diff must exceed to be considered too large to
           include in the email>
blacklist=<space-delimited list of shell glob patterns to consider
           sensitive>

Only 'email' is required.

The commit message can itself contain some magic that will influence
the email sent out. The following patterns are special:

* Subject: <subject>
  Use the specified text as the subject of the message. Otherwise, the
  first line (up to the first [.!;:?] or 120 characters) will be used.
* Resolve: <ticket number>
  Add some magic to the email that will resolve the specified RT ticket.

These patterns can either be listed on a line by themselves, or
enclosed in curly braces ({...}). Whitespace after the colon is
optional. The patterns are all case-insensitive. So these two commits
are identical:
 
svn ci -m '{resolve:108934}Fixed DNS error'
svn ci -m 'Fixed DNS error
Resolve: 108934'
"""

__author__ = "Chris St Pierre"
__email__ = "chris.a.st.pierre@gmail.com"

import re
import os
import sys
import ldap
import pysvn
import shutil
import fnmatch
import smtplib
import logging
import logging.handlers
import tempfile
import lxml.etree
from email.Message import Message
from optparse import OptionParser, OptionError
from ConfigParser import SafeConfigParser

SEPARATOR = "=" * 67

LOGGER = None

def get_logger(verbose=0):
    """ set up logging according to the verbose level given on the
    command line """
    global LOGGER
    if LOGGER is None:
        LOGGER = logging.getLogger(sys.argv[0])
        stderr = logging.StreamHandler()
        level = logging.WARNING
        lformat = "%(message)s"
        if verbose == 1:
            level = logging.INFO
        elif verbose > 1:
            stderr.setFormatter(logging.Formatter("%(asctime)s: %(levelname)s: %(message)s"))
            level = logging.DEBUG
        LOGGER.setLevel(level)
        LOGGER.addHandler(stderr)
        syslog = logging.handlers.SysLogHandler("/dev/log")
        syslog.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        LOGGER.addHandler(syslog)
        LOGGER.debug("Setting verbose to %s" % verbose)
    return LOGGER

def parse_log_message(message):
    """ Parse the commit log message """
    keywords = dict(subject=None, resolve=None)
    logger = get_logger()
    for keyword in keywords.iterkeys():
        pattern = re.compile((r'(?:\A|\n|\{)%s:\s*([^\}\n]+)(?:\Z|\n|\})' %
                              keyword),
                             re.IGNORECASE | re.MULTILINE)
        match = pattern.search(message)
        if match:
            keywords[keyword] = match.group(1).strip()
            logger.debug("Found log message keyword %s=%s" % (keyword,
                                                              match.group(0)))
            message = pattern.sub('', message)
    return (message, keywords)

def build_summary(changes):
    """ build a summary of changes """
    summary = dict()
    logger = get_logger()
    for change in changes:
        logger.info("Summarizing %s file %s" % (change.summarize_kind,
                                                change.path))
        if change.summarize_kind not in summary:
            summary[change.summarize_kind] = []
        summary[change.summarize_kind].append(change.path)
    return summary

def get_author_email(author):
    """looks up author email in ldap"""
    logger = get_logger()
    ldapconf = dict()
    for conffile in ["/etc/ldap.conf", "/etc/openldap/ldap.conf",
                     "/etc/nss_ldap.conf"]:
        # short-circuit if we have both a base and a host
        if 'base' in ldapconf and 'host' in ldapconf:
            break
        logger.debug("Reading LDAP configuration from %s" % conffile)
        try:
            for line in open(conffile).read().splitlines():
                match = re.search(r'^(base|host|ssl)\s+(.*)', line)
                if match:
                    ldapconf[match.group(1)] = match.group(2)
        except IOError:
            pass

    if 'base' in ldapconf and 'host' in ldapconf:
	    # host can be a space-delimited list; in that case, we just
	    # use the first host
        ldapconf['host'] = ldapconf['host'].split()[0]

        # ensure that we have an ldap uri
        if not re.search(r'^ldap[si]?://', ldapconf['host']):
            if ('ssl' in ldapconf and
                ldapconf['ssl'] in ['on', 'yes', 'start_tls']):
                ldapconf['host'] = "ldaps://%s" % ldapconf['host']
            else:
                ldapconf['host'] = "ldap://%s" % ldapconf['host']

        logger.debug("Connecting to LDAP server at %s" % ldapconf['host'])
        try:
            conn = ldap.initialize(ldapconf['host'])
        except ldap.LDAPError, err:
            logger.warn("Could not connect to LDAP server at %s: %s" %
                        (ldapconf['host'], err))
            return author

        if 'ssl' in ldapconf and ldapconf['ssl'] == 'start_tls':
            # try TLS, but don't require it.  if starting TLS fails
            # but the connection requires confidentiality, the search
            # will fail below
            logger.debug("Starting TLS")
            try:
                conn.start_tls_s()
            except ldap.LDAPError, err:
                if err[0]['info'] != 'TLS already started':
                    logger.warn("Could not start TLS: %s" % err)

        ldap_filter = "uid=%s" % author
        logger.debug("Searching for %s in %s" % (ldap_filter, ldapconf['base']))
        try:
            res = conn.search_s(ldapconf['base'], ldap.SCOPE_SUBTREE,
                                ldap_filter, ['mail'])
            if len(res) == 1:
                attrs = res.pop()[1]
                logger.debug("Got %s for email address" % attrs['mail'][0])
                return attrs['mail'][0]
            elif len(res):
                logger.warn("More than one LDAP entry found for %s" %
                             ldap_filter)
                return author
            elif not res:
                logger.warn("No LDAP entries found for %s" % ldap_filter)
                return author
        except ldap.LDAPError, err:
            logger.warn("Could not search for %s in LDAP at %s: %s" %
                        (ldap_filter, ldapconf['host'], err))
            return author
    else:
        logger.warn("Could not determine LDAP configuration")
        return author

def get_diff_set(change, baseuri, largediff=100, rev=None,
                 blacklist=None):
    """ generate diffs for the given change object.  returns a tuple
    of (<diff type>, <diff data>).  Type is one of None, 'sensitive',
    'large', 'binary', or 'diff'"""
    logger = get_logger()

    client = pysvn.Client()
    revision = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
    previous = pysvn.Revision(pysvn.opt_revision_kind.number, rev - 1)

    logger.info("Diffing %s file %s" % (change.summarize_kind, change.path))
    change_uri = os.path.join(baseuri, change.path)

    if plugin_blacklist is None:
        plugin_blacklist = []

    # There are a number of reasons a diff might not be included in an
    # svnlog message:
    #
    # * The file was deleted
    # * The file matches a blacklist pattern (default */Ohai/*.json,
    #   */Probes/probed.xml, */SSHbase/*, */Packages/packages.conf)
    # * The file is a directory, not a file
    # * The file is binary
    # * The diff exceeds 100 lines
    # * The file is a Property file and is flagged as sensitive in the
    #   opening Property tag
    # * The file is flagged as sensitive in its info.xml
    #
    # These are listed here in approximate order from least expensive
    # to most expensive.  Consequently, if we can do a simple filename
    # match and avoid generating a diff, we win; and so on.

    if change.summarize_kind == pysvn.diff_summarize_kind.delete:
        logger.debug("%s was %s, skipping diff" % (change.path,
                                                   change.summarize_kind))
        return (None, None)

    if ("/SSHbase/" in change.path or
        change.path.endswith("/Packages/packages.conf")):
        logger.debug("%s is hard-coded as sensitive, skipping diff" %
                     change.path)
        return ("sensitive", change.path)

    for pattern in blacklist:
        if fnmatch.fnmatch(change.path, pattern):
            logger.debug("% is blacklisted, skipping diff")
            return (None, None)

    info = client.info2(change_uri, revision=revision, recurse=False)[0][1]
    if info.kind == pysvn.node_kind.dir:
        logger.debug("%s is a directory, skipping diff" % change.path)
        return (None, None)

    mime = client.propget('svn:mime-type', change_uri, revision=revision)
    if change_uri in mime:
        logger.debug("%s is binary (%s), skipping diff" %
                     (change.path, mime[change_uri]))
        return ('binary', change.path)

    diff = None
    if change.summarize_kind == pysvn.diff_summarize_kind.modified:
        tempdir = tempfile.mkdtemp()
        diff = client.diff(tempdir, change_uri,
                           revision1=previous,
                           revision2=revision)
        shutil.rmtree(tempdir)
    else:
        diff = ("Added: %s\n%s\n%s" %
                (change.path, SEPARATOR,
                 client.cat(change_uri, revision=revision)))
    
    if len(diff.splitlines()) > largediff:
        logger.debug("Diff for %s is large (%d lines), skipping diff" %
                     (change.path, len(diff.splitlines())))
        return ('large', change.path)
    
    if fnmatch.fnmatch(change.path, "*/Properties/*.xml"):
        logger.info("Checking out %s" % os.path.dirname(change.path))
        tempdir = tempfile.mkdtemp()
        try:
            client.checkout(os.path.join(baseuri, os.path.dirname(change.path)),
                            tempdir, revision=revision)
            xdata = \
                lxml.etree.parse(os.path.join(tempdir,
                                              os.path.basename(change.path)))
        finally:
            shutil.rmtree(tempdir)
        if xdata.getroot().get("sensitive", "false").lower() == "true":
            return ("sensitive", change.path)

    if ("/Cfg/" in change.path and
        os.path.basename(change.path) != "info.xml"):
        # try to check out an info.xml for this file
        logger.info("Checking out %s" % os.path.dirname(change.path))
        tempdir = tempfile.mkdtemp()
        # in python 2.4, try...except...finally isn't supported; you
        # have to nest a try...except block inside try...finally
        try:
            try:
                client.checkout(os.path.join(baseuri,
                                             os.path.dirname(change.path)),
                                tempdir, revision=revision)
                root = lxml.etree.parse(os.path.join(tempdir,
                                                     "info.xml")).getroot()
            except IOError:
                logger.debug("No info.xml found for %s" % change.path)
            except:
                raise
        finally:
            shutil.rmtree(tempdir)

        if root is not None:
            for el in root.xpath("//Info"):
                if el.get("sensitive", "false").lower() == "true":
                    return ("sensitive", change.path)

    return ('diff', diff)

def parse_args():
    """ parse command-line arguments """
    usage = """Usage: bcfg2_svnlog.py [options] -r <revision> <repos>"""
    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", help="Be verbose", action="count")
    parser.add_option("-c", "--config", help="Config file",
                      default="/etc/bcfg2_svnlog.conf")
    parser.add_option("-r", "--rev", help="Revision")
    parser.add_option("--stdout", help="Print log message to stdout")
    try:
        (options, args) = parser.parse_args()
    except OptionError:
        parser.print_help()
        raise SystemExit(1)

    if not len(args):
        parser.print_help()
        raise SystemExit(1)

    get_logger(options.verbose)
    return (options, args.pop())

def get_config(configfile, repos_name):
    """ read config for the given repository """
    logger = get_logger()
    defaults = dict(largediff=100,
                    subject='',
                    blacklist="*/Ohai/*.json */Probes/probed.xml */SSHbase/ssh_host*_key.[GH]* */Packages/packages.conf")
    config = SafeConfigParser(defaults)
    if os.path.exists(configfile):
        config.read(configfile)
    else:
        logger.fatal("Config file %s does not exist" % configfile)
        raise SystemExit(1)

    if not config.has_section(repos_name):
        logger.fatal("No configuration section found for '%s' repo, aborting" %
                     repos_name)
        raise SystemExit(2)

    return config

def main():
    """ main subroutine """
    (options, path) = parse_args()
    uri = "file://%s" % path
    logger = get_logger()

    repos_name = os.path.basename(uri)
    config = get_config(options.config, repos_name)
    
    client = pysvn.Client()
    revision = pysvn.Revision(pysvn.opt_revision_kind.number, options.rev)
    previous = pysvn.Revision(pysvn.opt_revision_kind.number,
                              int(options.rev) - 1)
    changes = client.diff_summarize(uri,
                                    revision1=previous,
                                    revision2=revision)

    # parse log message
    log = client.log(uri, revision_end=revision)[0]
    logger.info("Examining commit %s by %s" % (options.rev, log.author))
    (message, keywords) = parse_log_message(log.message)

    summary = build_summary(changes)

    diffs = dict(diff=[], large=[], binary=[], sensitive=[])
    for change in changes:
        (dtype, ddata) = get_diff_set(change, uri,
                                      rev=int(options.rev),
                                      largediff=int(config.get(repos_name,
                                                               'largediff')))
        if dtype is not None:
            diffs[dtype].append(ddata)

    # construct the email
    body = [message.strip(),
            '',
            "Author: %s" % log.author,
            "Revision: %s" % options.rev,
            '',
            "Affected files:", '']
    for ctype in summary:
        body.extend(["%-65s %-10s" % (f, ctype) for f in summary[ctype]])
    body.append('')

    if diffs['binary']:
        body.extend([SEPARATOR, '', "The following binary files were changed:",
                     ''])
        body.extend(diffs['binary'])
        body.append('')

    if diffs['large']:
        body.extend([SEPARATOR, '',
                     "Diffs for the following files were too large to include:",
                     ''])
        body.extend(diffs['large'])
        body.append('')
        
    if diffs['sensitive']:
        body.extend([SEPARATOR, '',
                     "The following sensitive files were changed:", ''])
        body.extend(diffs['sensitive'])
        body.append('')

    if diffs['diff']:
        body.extend([SEPARATOR, '', "The following files were changed:", ''])
        body.extend(diffs['diff'])

    if keywords['resolve']:
        body.extend(['',
                     "RT-AddRefersTo: %s" % keywords['resolve'],
                     "RT-AddReferredToBy: %s" % keywords['resolve'],
                     "RT-ResolveTicket: %s" % keywords['resolve']])

    if config.has_option(repos_name, 'email') and not options.stdout:
        msg = Message()
        msg.set_payload("\n".join(body))
        subject = None
        if keywords['subject']:
            subject = keywords['subject']
        elif "\n" in message:
            subject = message[0:max(120, message.index("\n"))]
        else:
            subject = message[0:120]
        msg['Subject'] = "%s %s" % (config.get(repos_name, 'subject'), subject)

        msg['From'] = get_author_email(log.author)
        msg['To'] = config.get(repos_name, 'email')

        logger.debug("Sending message from %s to %s: %s" % (msg['From'],
                                                            msg['To'],
                                                            msg['Subject']))
        smtp = smtplib.SMTP('localhost')
        if options.verbose > 2:
            # this is _really_ verbose
            smtp.set_debuglevel(options.verbose - 1)
        smtp.sendmail(msg['From'], [msg['To']], msg.as_string())
        smtp.quit()
    else:
        print("\n".join(body))
 
if __name__ == "__main__":
    sys.exit(main())


