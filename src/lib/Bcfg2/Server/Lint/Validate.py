""" Ensure that the repo validates """

import os
import sys
import glob
import fnmatch
import lxml.etree
from subprocess import Popen, PIPE, STDOUT
import Bcfg2.Server.Lint


class Validate(Bcfg2.Server.Lint.ServerlessPlugin):
    """ Ensure that the repo validates """

    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerlessPlugin.__init__(self, *args, **kwargs)
        self.filesets = \
            {"Metadata/groups.xml": "metadata.xsd",
             "Metadata/clients.xml": "clients.xsd",
             "Cfg/**/info.xml": "info.xsd",
             "Cfg/**/privkey.xml": "privkey.xsd",
             "Cfg/**/pubkey.xml": "pubkey.xsd",
             "Cfg/**/authorizedkeys.xml": "authorizedkeys.xsd",
             "Cfg/**/authorized_keys.xml": "authorizedkeys.xsd",
             "SSHbase/**/info.xml": "info.xsd",
             "SSLCA/**/info.xml": "info.xsd",
             "TGenshi/**/info.xml": "info.xsd",
             "TCheetah/**/info.xml": "info.xsd",
             "Bundler/*.xml": "bundle.xsd",
             "Bundler/*.genshi": "bundle.xsd",
             "Pkgmgr/*.xml": "pkglist.xsd",
             "Base/*.xml": "base.xsd",
             "Rules/*.xml": "rules.xsd",
             "Defaults/*.xml": "defaults.xsd",
             "etc/report-configuration.xml": "report-configuration.xsd",
             "Deps/*.xml": "deps.xsd",
             "Decisions/*.xml": "decisions.xsd",
             "Packages/sources.xml": "packages.xsd",
             "GroupPatterns/config.xml": "grouppatterns.xsd",
             "NagiosGen/config.xml": "nagiosgen.xsd",
             "FileProbes/config.xml": "fileprobes.xsd",
             "SSLCA/**/cert.xml": "sslca-cert.xsd",
             "SSLCA/**/key.xml": "sslca-key.xsd"
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
                schemafile = os.path.join(schemadir, schemaname)
                schema = self._load_schema(schemafile)
                if schema:
                    for filename in filelist:
                        self.validate(filename, schemafile, schema=schema)

        self.check_properties()

    @classmethod
    def Errors(cls):
        return {"schema-failed-to-parse": "warning",
                "properties-schema-not-found": "warning",
                "xml-failed-to-parse": "error",
                "xml-failed-to-read": "error",
                "xml-failed-to-verify": "error",
                "input-output-error": "error"}

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
            schema = self._load_schema(schemafile)
            if not schema:
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
            listfiles = lambda p: fnmatch.filter(self.files,
                                                 os.path.join('*', p))
        else:
            listfiles = lambda p: glob.glob(os.path.join(self.config['repo'],
                                                         p))

        for path in self.filesets.keys():
            if '/**/' in path:
                if self.files is not None:
                    self.filelists[path] = listfiles(path)
                else:  # self.files is None
                    fpath, fname = path.split('/**/')
                    self.filelists[path] = []
                    for root, _, files in \
                            os.walk(os.path.join(self.config['repo'],
                                                 fpath)):
                        self.filelists[path].extend([os.path.join(root, f)
                                                     for f in files
                                                     if f == fname])
            else:
                self.filelists[path] = listfiles(path)

        self.filelists['props'] = listfiles("Properties/*.xml")

    def _load_schema(self, filename):
        """ load an XML schema document, returning the Schema object """
        try:
            return lxml.etree.XMLSchema(lxml.etree.parse(filename))
        except IOError:
            err = sys.exc_info()[1]
            self.LintError("input-output-error", str(err))
        except lxml.etree.XMLSchemaParseError:
            err = sys.exc_info()[1]
            self.LintError("schema-failed-to-parse",
                           "Failed to process schema %s: %s" %
                           (filename, err))
        return None
