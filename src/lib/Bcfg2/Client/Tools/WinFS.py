"""All Windows Type client support for Bcfg2."""
import sys
import os
import stat
import tempfile
import Bcfg2.Options
import Bcfg2.Client.Tools


class WinFS(Bcfg2.Client.Tools.Tool):
    """Windows File support code."""
    name = 'WinFS'
    __handles__ = [('Path', 'file')]

    def __init__(self, config):
        Bcfg2.Client.Tools.Tool.__init__(self, config)
        self.__req__ = dict(Path=dict())
        self.__req__['Path']['file'] = ['name', 'mode', 'owner', 'group']
    
    def _getFilePath(self, entry):
        filePath = os.path.expandvars(os.path.normpath(entry.get('name')[1:]))
        if(not filePath[1] == ':'):
            self.logger.info("Skipping \"%s\" because it doesnt look like a Windows Path" % filePath)
            return False
        return filePath
        
    def VerifyPath(self, entry, _):
        """Path always verify true."""
        filePath = self._getFilePath(entry)
        if(not filePath):
            return False
        ondisk = self._exists(filePath)
        tempdata, is_binary = self._get_data(entry)
        if isinstance(tempdata, str) and str != unicode:
            tempdatasize = len(tempdata)
        else:
            tempdatasize = len(tempdata.encode(Bcfg2.Options.setup.encoding))

        different = False
        content = None
        if not ondisk:
            # first, see if the target file exists at all; if not,
            # they're clearly different
            different = True
            content = ""
        elif tempdatasize != ondisk[stat.ST_SIZE]:
            # next, see if the size of the target file is different
            # from the size of the desired content
            different = True
        else:
            # finally, read in the target file and compare them
            # directly. comparison could be done with a checksum,
            # which might be faster for big binary files, but slower
            # for everything else
            try:
                content = open(filePath).read()
            except UnicodeDecodeError:
                content = open(filePath,
                               encoding=Bcfg2.Options.setup.encoding).read()
            except IOError:
                self.logger.error("Windows: Failed to read %s: %s" %
                                  (filePath, sys.exc_info()[1]))
                return False
            different = str(content) != str(tempdata)
        return not different
        
    def InstallPath(self, entry):
        """Install device entries."""
        filePath = self._getFilePath(entry)

        if not filePath:
            return False
        
        self.logger.debug("Installing: " + filePath)
        if not os.path.exists(os.path.dirname(filePath)):
            if not self._makedirs(path=filePath):
                return False
        newfile = self._write_tmpfile(entry, filePath)
        if not newfile:
            return False
        rv = True
        if not self._rename_tmpfile(newfile, filePath):
            return False

        return rv

    def _makedirs(self, path):
        """ os.makedirs helpfully creates all parent directories for us."""
        created = []
        cur = path
        #while cur and cur != '/':
        #    if not os.path.exists(cur):
        #        created.append(cur)
        #    cur = os.path.dirname(cur)
        rv = True
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error('Windows: Failed to create directory %s: %s' %
                              (path, err))
            rv = False
        return rv

    def _write_tmpfile(self, entry, filePath):
        """ Write the file data to a temp file """
        filedata = self._get_data(entry)[0]
        # get a temp file to write to that is in the same directory as
        # the existing file in order to preserve any permissions
        # protections on that directory, and also to avoid issues with
        # /tmp set nosetuid while creating files that are supposed to
        # be setuid
        try:
            (newfd, newfile) = \
                tempfile.mkstemp(prefix=os.path.basename(filePath),
                                 dir=os.path.dirname(filePath))
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Windows: Failed to create temp file in %s: %s" % (filePath, err))
            return False
        try:
            if isinstance(filedata, str) and str != unicode:
                os.fdopen(newfd, 'w').write(filedata)
            else:
                os.fdopen(newfd, 'wb').write(
                    filedata.encode(Bcfg2.Options.setup.encoding))
        except (OSError, IOError):
            err = sys.exc_info()[1]
            self.logger.error("Windows: Failed to open temp file %s for writing "
                              "%s: %s" %
                              (newfile, filePath, err))
            return False
        return newfile

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
                    tempdata = tempdata.encode(Bcfg2.Options.setup.encoding)
                except UnicodeEncodeError:
                    err = sys.exc_info()[1]
                    self.logger.error("Windows: Error encoding file %s: %s" %
                                      (entry.get('name'), err))
        return (tempdata, is_binary)
        
    def _rename_tmpfile(self, newfile, filePath):
        """ Rename the given file to the appropriate filename for entry """
        try:
            if(os.path.isfile(filePath)):
                os.unlink(filePath)
            os.rename(newfile, filePath)
            return True
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Windows: Failed to rename temp file %s to %s: %s"
                              % (newfile, filePath, err))
            try:
                os.unlink(newfile)
            except OSError:
                err = sys.exc_info()[1]
                self.logger.error("Windows: Could not remove temp file %s: %s" %
                                  (newfile, err))
            return False
            
    def _exists(self, filePath):
        """ check for existing paths and optionally remove them.  if
        the path exists, return the lstat of it """
        try:
            return os.lstat(filePath)
        except OSError:
            return None
