import fnmatch
import glob
import lxml.etree
import os
from subprocess import Popen, PIPE, STDOUT
import sys

import Bcfg2.Server.Lint

class Validate(Bcfg2.Server.Lint.ServerlessPlugin):
    """ Ensure that the repo validates """

    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerlessPlugin.__init__(self, *args, **kwargs)
        self.filesets = {"metadata:groups":"%s/metadata.xsd",
                         "metadata:clients":"%s/clients.xsd",
                         "info":"%s/info.xsd",
                         "%s/Bundler/*.xml":"%s/bundle.xsd",
                         "%s/Bundler/*.genshi":"%s/bundle.xsd",
                         "%s/Pkgmgr/*.xml":"%s/pkglist.xsd",
                         "%s/Base/*.xml":"%s/base.xsd",
                         "%s/Rules/*.xml":"%s/rules.xsd",
                         "%s/Defaults/*.xml":"%s/defaults.xsd",
                         "%s/etc/report-configuration.xml":"%s/report-configuration.xsd",
                         "%s/Svcmgr/*.xml":"%s/services.xsd",
                         "%s/Deps/*.xml":"%s/deps.xsd",
                         "%s/Decisions/*.xml":"%s/decisions.xsd",
                         "%s/Packages/sources.xml":"%s/packages.xsd",
                         "%s/GroupPatterns/config.xml":"%s/grouppatterns.xsd",
                         "%s/NagiosGen/config.xml":"%s/nagiosgen.xsd",
                         "%s/FileProbes/config.xml":"%s/fileprobes.xsd",
                         }

        self.filelists = {}
        self.get_filelists()

    def Run(self):
        schemadir = self.config['schema']
        
        for path, schemaname in self.filesets.items():
            try:
                filelist = self.filelists[path]
            except KeyError:
                filelist = []

            if filelist:
                # avoid loading schemas for empty file lists
                schemafile = schemaname % schemadir
                try:
                    schema = lxml.etree.XMLSchema(lxml.etree.parse(schemafile))
                except IOError:
                    e = sys.exc_info()[1]
                    self.LintError("input-output-error", str(e))
                    continue
                except lxml.etree.XMLSchemaParseError:
                    e = sys.exc_info()[1]
                    self.LintError("schema-failed-to-parse",
                                   "Failed to process schema %s: %s" %
                                   (schemafile, e))
                    continue
                for filename in filelist:
                    self.validate(filename, schemafile, schema=schema)

        self.check_properties()

    def check_properties(self):
        """ check Properties files against their schemas """
        for filename in self.filelists['props']:
            schemafile = "%s.xsd" % os.path.splitext(filename)[0]
            if os.path.exists(schemafile):
                self.validate(filename, schemafile)
            else:
                self.LintError("properties-schema-not-found",
                               "No schema found for %s" % filename)

    def validate(self, filename, schemafile, schema=None):
        """validate a file against the given lxml.etree.Schema.
        return True on success, False on failure """
        if schema is None:
            # if no schema object was provided, instantiate one
            try:
                schema = lxml.etree.XMLSchema(lxml.etree.parse(schemafile))
            except:
                self.LintError("schema-failed-to-parse",
                               "Failed to process schema %s" % schemafile)
                return False

        try:
            datafile = lxml.etree.parse(filename)
        except SyntaxError:
            lint = Popen(["xmllint", filename], stdout=PIPE, stderr=STDOUT)
            self.LintError("xml-failed-to-parse",
                           "%s fails to parse:\n%s" % (filename,
                                                       lint.communicate()[0]))
            lint.wait()
            return False
        except IOError:
            self.LintError("xml-failed-to-read",
                           "Failed to open file %s" % filename)
            return False
    
        if not schema.validate(datafile):
            cmd = ["xmllint"]
            if self.files is None:
                cmd.append("--xinclude")
            cmd.extend(["--noout", "--schema", schemafile, filename])
            lint = Popen(cmd, stdout=PIPE, stderr=STDOUT)
            output = lint.communicate()[0]
            if lint.wait():
                self.LintError("xml-failed-to-verify",
                               "%s fails to verify:\n%s" % (filename, output))
                return False
        return True

    def get_filelists(self):
        """ get lists of different kinds of files to validate """
        if self.files is not None:
            listfiles = lambda p: fnmatch.filter(self.files, p % "*")
        else:
            listfiles = lambda p: glob.glob(p % self.config['repo'])

        for path in self.filesets.keys():
            if path.startswith("metadata:"):
                mtype = path.split(":")[1]
                self.filelists[path] = self.get_metadata_list(mtype)
            elif path == "info":
                if self.files is not None:
                    self.filelists[path] = \
                                         [f for f in self.files
                                          if os.path.basename(f) == 'info.xml']
                else: # self.files is None
                    self.filelists[path] = []
                    for infodir in ['Cfg', 'TGenshi', 'TCheetah']:
                        for root, dirs, files in os.walk('%s/%s' %
                                                         (self.config['repo'],
                                                          infodir)):
                            self.filelists[path].extend([os.path.join(root, f)
                                                         for f in files
                                                         if f == 'info.xml'])
            else:
                self.filelists[path] = listfiles(path)

        self.filelists['props'] = listfiles("%s/Properties/*.xml")
        all_metadata = listfiles("%s/Metadata/*.xml")

        # if there are other files in Metadata that aren't xincluded
        # from clients.xml or groups.xml, we can't verify them.  warn
        # about those.
        for fname in all_metadata:
            if (fname not in self.filelists['metadata:groups'] and
                fname not in self.filelists['metadata:clients']):
                self.LintError("broken-xinclude-chain",
                               "Broken XInclude chain: Could not determine file type of %s" % fname)

    def get_metadata_list(self, mtype):
        """ get all metadata files for the specified type (clients or
        group) """
        if self.files is not None:
            rv = fnmatch.filter(self.files, "*/Metadata/%s.xml" % mtype)
        else:
            rv = glob.glob("%s/Metadata/%s.xml" % (self.config['repo'], mtype))

        # attempt to follow XIncludes.  if the top-level files aren't
        # listed in self.files, though, there's really nothing we can
        # do to guess what a file in Metadata is
        if rv:
            try:
                rv.extend(self.follow_xinclude(rv[0]))
            except lxml.etree.XMLSyntaxError:
                e = sys.exc_info()[1]
                self.LintError("xml-failed-to-parse",
                               "%s fails to parse:\n%s" % (rv[0], e))


        return rv

    def follow_xinclude(self, xfile):
        """ follow xincludes in the given file """
        xdata = lxml.etree.parse(xfile)
        included = set([ent.get('href') for ent in
                        xdata.findall('./{http://www.w3.org/2001/XInclude}include')])
        rv = []
        
        while included:
            try:
                filename = included.pop()
            except KeyError:
                continue

            path = os.path.join(os.path.dirname(xfile), filename)
            if self.HandlesFile(path):
                rv.append(path)
                groupdata = lxml.etree.parse(path)
                [included.add(el.get('href'))
                 for el in
                 groupdata.findall('./{http://www.w3.org/2001/XInclude}include')]
                included.discard(filename)

        return rv

