""" Handle <Path type='file' ...> entries """

import os
import sys
import stat
import time
import difflib
import tempfile
from Bcfg2.Client.Tools.POSIX.base import POSIXTool
from Bcfg2.Compat import unicode, b64encode, b64decode  # pylint: disable=W0622


class POSIXFile(POSIXTool):
    """ Handle <Path type='file' ...> entries """
    __req__ = ['name', 'mode', 'owner', 'group']

    def fully_specified(self, entry):
        return entry.text is not None or entry.get('empty', 'false') == 'true'

    def _is_string(self, strng, encoding):
        """ Returns true if the string contains no ASCII control
        characters and can be decoded from the specified encoding. """
        for char in strng:
            if ord(char) < 9 or ord(char) > 13 and ord(char) < 32:
                return False
        if not hasattr(strng, "decode"):
            # py3k
            return True
        try:
            strng.decode(encoding)
            return True
        except:  # pylint: disable=W0702
            return False

    def _get_data(self, entry):
        """ Get a tuple of (<file data>, <is binary>) for the given entry """
        is_binary = entry.get('encoding', 'ascii') == 'base64'
        if entry.get('empty', 'false') == 'true' or not entry.text:
            tempdata = ''
        elif is_binary:
            tempdata = b64decode(entry.text)
        else:
            tempdata = entry.text
            if isinstance(tempdata, unicode) and unicode != str:
                try:
                    tempdata = tempdata.encode(self.setup['encoding'])
                except UnicodeEncodeError:
                    err = sys.exc_info()[1]
                    self.logger.error("POSIX: Error encoding file %s: %s" %
                                      (entry.get('name'), err))
        return (tempdata, is_binary)

    def verify(self, entry, modlist):
        ondisk = self._exists(entry)
        tempdata, is_binary = self._get_data(entry)

        different = False
        content = None
        if not ondisk:
            # first, see if the target file exists at all; if not,
            # they're clearly different
            different = True
            content = ""
        elif len(tempdata) != ondisk[stat.ST_SIZE]:
            # next, see if the size of the target file is different
            # from the size of the desired content
            different = True
        else:
            # finally, read in the target file and compare them
            # directly. comparison could be done with a checksum,
            # which might be faster for big binary files, but slower
            # for everything else
            try:
                content = open(entry.get('name')).read()
            except IOError:
                self.logger.error("POSIX: Failed to read %s: %s" %
                                  (entry.get("name"), sys.exc_info()[1]))
                return False
            different = content != tempdata

        if different:
            self.logger.debug("POSIX: %s has incorrect contents" %
                              entry.get("name"))
            self._get_diffs(
                entry, interactive=self.setup['interactive'],
                sensitive=entry.get('sensitive', 'false').lower() == 'true',
                is_binary=is_binary, content=content)
        return POSIXTool.verify(self, entry, modlist) and not different

    def _write_tmpfile(self, entry):
        """ Write the file data to a temp file """
        filedata, _ = self._get_data(entry)
        # get a temp file to write to that is in the same directory as
        # the existing file in order to preserve any permissions
        # protections on that directory, and also to avoid issues with
        # /tmp set nosetuid while creating files that are supposed to
        # be setuid
        try:
            (newfd, newfile) = \
                tempfile.mkstemp(prefix=os.path.basename(entry.get("name")),
                                 dir=os.path.dirname(entry.get("name")))
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("POSIX: Failed to create temp file in %s: %s" %
                              (os.path.dirname(entry.get('name')), err))
            return False
        try:
            os.fdopen(newfd, 'w').write(filedata)
        except (OSError, IOError):
            err = sys.exc_info()[1]
            self.logger.error("POSIX: Failed to open temp file %s for writing "
                              "%s: %s" %
                              (newfile, entry.get("name"), err))
            return False
        return newfile

    def _rename_tmpfile(self, newfile, entry):
        """ Rename the given file to the appropriate filename for entry """
        try:
            os.rename(newfile, entry.get('name'))
            return True
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("POSIX: Failed to rename temp file %s to %s: %s"
                              % (newfile, entry.get('name'), err))
            try:
                os.unlink(newfile)
            except OSError:
                err = sys.exc_info()[1]
                self.logger.error("POSIX: Could not remove temp file %s: %s" %
                                  (newfile, err))
            return False

    def install(self, entry):
        """Install device entries."""
        if not os.path.exists(os.path.dirname(entry.get('name'))):
            if not self._makedirs(entry,
                                  path=os.path.dirname(entry.get('name'))):
                return False
        newfile = self._write_tmpfile(entry)
        if not newfile:
            return False
        rv = self._set_perms(entry, path=newfile)
        if not self._rename_tmpfile(newfile, entry):
            return False

        return POSIXTool.install(self, entry) and rv

    def _get_diffs(self, entry, interactive=False,  # pylint: disable=R0912
                   sensitive=False, is_binary=False, content=None):
        """ generate the necessary diffs for entry """
        if not interactive and sensitive:
            return

        prompt = [entry.get('qtext', '')]
        attrs = dict()
        if content is None:
            # it's possible that we figured out the files are
            # different without reading in the local file.  if the
            # supplied version of the file is not binary, we now have
            # to read in the local file to figure out if _it_ is
            # binary, and either include that fact or the diff in our
            # prompts for -I and the reports
            try:
                content = open(entry.get('name')).read()
            except UnicodeDecodeError:
                content = open(entry.get('name'), encoding='utf-8').read()
            except IOError:
                self.logger.error("POSIX: Failed to read %s: %s" %
                                  (entry.get("name"), sys.exc_info()[1]))
                return False
        if not is_binary:
            is_binary |= not self._is_string(content, self.setup['encoding'])
        if is_binary:
            # don't compute diffs if the file is binary
            prompt.append('Binary file, no printable diff')
            attrs['current_bfile'] = b64encode(content)
        else:
            if interactive:
                diff = self._diff(content, self._get_data(entry)[0],
                                  difflib.unified_diff,
                                  filename=entry.get("name"))
                if diff:
                    udiff = '\n'.join(l.rstrip('\n') for l in diff)
                    if hasattr(udiff, "decode"):
                        udiff = udiff.decode(self.setup['encoding'])
                    try:
                        prompt.append(udiff)
                    except UnicodeEncodeError:
                        prompt.append("Could not encode diff")
                elif entry.get("empty", "true"):
                    # the file doesn't exist on disk, but there's no
                    # expected content
                    prompt.append("%s does not exist" % entry.get("name"))
                else:
                    prompt.append("Diff took too long to compute, no "
                                  "printable diff")
            if not sensitive:
                diff = self._diff(content, self._get_data(entry)[0],
                                  difflib.ndiff, filename=entry.get("name"))
                if diff:
                    attrs["current_bdiff"] = b64encode("\n".join(diff))
                else:
                    attrs['current_bfile'] = b64encode(content)
        if interactive:
            entry.set("qtext", "\n".join(prompt))
        if not sensitive:
            for attr, val in attrs.items():
                entry.set(attr, val)

    def _diff(self, content1, content2, difffunc, filename=None):
        """ Return a diff of the two strings, as produced by difffunc.
        warns after 5 seconds and times out after 30 seconds. """
        rv = []
        start = time.time()
        longtime = False
        for diffline in difffunc(content1.split('\n'),
                                 content2.split('\n')):
            now = time.time()
            rv.append(diffline)
            if now - start > 5 and not longtime:
                if filename:
                    self.logger.info("POSIX: Diff of %s taking a long time" %
                                     filename)
                else:
                    self.logger.info("POSIX: Diff taking a long time")
                longtime = True
            elif now - start > 30:
                if filename:
                    self.logger.error("POSIX: Diff of %s took too long; "
                                      "giving up" % filename)
                else:
                    self.logger.error("POSIX: Diff took too long; giving up")
                return False
        return rv
