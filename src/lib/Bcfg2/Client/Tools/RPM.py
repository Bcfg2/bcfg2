"""Bcfg2 Support for RPMS"""

import os
import rpm
import Bcfg2.Client.Tools
import grp
import optparse
import pwd
import stat
import sys
try:
    import hashlib
    py24compat = False
except ImportError:
    # FIXME: Remove when client python dep is 2.5 or greater
    py24compat = True
    import md5

# Determine what prelink tools we have available.
# The isprelink module is a python extension that examines the ELF headers
# to see if the file has been prelinked.  If it is not present a lot of files
# are unnecessarily run through the prelink command.
try:
    from isprelink import *
    isprelink_imported = True
except ImportError:
    isprelink_imported = False

# If the prelink command is installed on the system then we need to do
# prelink -y on files.
if os.access('/usr/sbin/prelink', os.X_OK):
    prelink_exists = True
else:
    prelink_exists = False

# If we don't have isprelink then we will use the prelink configuration file to
# filter what we have to put through prelink -y.
import re
blacklist = []
whitelist = []
try:
    f = open('/etc/prelink.conf', mode='r')
    for line in f:
        if line.startswith('#'):
            continue
        option, pattern = line.split()
        if pattern.startswith('*.'):
            pattern = pattern.replace('*.', '\.')
            pattern += '$'
        elif pattern.startswith('/'):
            pattern = '^' + pattern
        if option == '-b':
            blacklist.append(pattern)
        elif option == '-l':
            whitelist.append(pattern)
    f.close()
except IOError:
    pass

blacklist_re = re.compile('|'.join(blacklist))
whitelist_re = re.compile('|'.join(whitelist))

# Flags that are not defined in rpm-python.
# They are defined in lib/rpmcli.h
# Bit(s) for verifyFile() attributes.
#
RPMVERIFY_NONE            = 0                      #  /*!< */
RPMVERIFY_MD5             = 1          # 1 << 0    #  /*!< from %verify(md5) */
RPMVERIFY_FILESIZE        = 2          # 1 << 1    #  /*!< from %verify(size) */
RPMVERIFY_LINKTO          = 4          # 1 << 2    #  /*!< from %verify(link) */
RPMVERIFY_USER            = 8          # 1 << 3    #  /*!< from %verify(user) */
RPMVERIFY_GROUP           = 16         # 1 << 4    #  /*!< from %verify(group) */
RPMVERIFY_MTIME           = 32         # 1 << 5    #  /*!< from %verify(mtime) */
RPMVERIFY_MODE            = 64         # 1 << 6    #  /*!< from %verify(mode) */
RPMVERIFY_RDEV            = 128        # 1 << 7    #  /*!< from %verify(rdev) */
RPMVERIFY_CONTEXTS        = 32768      # (1 << 15) #  /*!< from --nocontexts */
RPMVERIFY_READLINKFAIL    = 268435456  # (1 << 28) #  /*!< readlink failed */
RPMVERIFY_READFAIL        = 536870912  # (1 << 29) #  /*!< file read failed */
RPMVERIFY_LSTATFAIL       = 1073741824 # (1 << 30) #  /*!< lstat failed */
RPMVERIFY_LGETFILECONFAIL = 2147483648 # (1 << 31) #  /*!< lgetfilecon failed */

RPMVERIFY_FAILURES =    \
 (RPMVERIFY_LSTATFAIL|RPMVERIFY_READFAIL|RPMVERIFY_READLINKFAIL| \
  RPMVERIFY_LGETFILECONFAIL)

# Bit(s) to control rpm_verify() operation.
#
VERIFY_DEFAULT       = 0,       #  /*!< */
VERIFY_MD5           = 1 << 0   #  /*!< from --nomd5 */
VERIFY_SIZE          = 1 << 1   #  /*!< from --nosize */
VERIFY_LINKTO        = 1 << 2   #  /*!< from --nolinkto */
VERIFY_USER          = 1 << 3   #  /*!< from --nouser */
VERIFY_GROUP         = 1 << 4   #  /*!< from --nogroup */
VERIFY_MTIME         = 1 << 5   #  /*!< from --nomtime */
VERIFY_MODE          = 1 << 6   #  /*!< from --nomode */
VERIFY_RDEV          = 1 << 7   #  /*!< from --nodev */
#        /* bits 8-14 unused, reserved for rpmVerifyAttrs */
VERIFY_CONTEXTS      = 1 << 15  #  /*!< verify: from --nocontexts */
VERIFY_FILES         = 1 << 16  #  /*!< verify: from --nofiles */
VERIFY_DEPS          = 1 << 17  #  /*!< verify: from --nodeps */
VERIFY_SCRIPT        = 1 << 18  #  /*!< verify: from --noscripts */
VERIFY_DIGEST        = 1 << 19  #  /*!< verify: from --nodigest */
VERIFY_SIGNATURE     = 1 << 20  #  /*!< verify: from --nosignature */
VERIFY_PATCHES       = 1 << 21  #  /*!< verify: from --nopatches */
VERIFY_HDRCHK        = 1 << 22  #  /*!< verify: from --nohdrchk */
VERIFY_FOR_LIST      = 1 << 23  #  /*!< query:  from --list */
VERIFY_FOR_STATE     = 1 << 24  #  /*!< query:  from --state */
VERIFY_FOR_DOCS      = 1 << 25  #  /*!< query:  from --docfiles */
VERIFY_FOR_CONFIG    = 1 << 26  #  /*!< query:  from --configfiles */
VERIFY_FOR_DUMPFILES = 1 << 27  #  /*!< query:  from --dump */
#        /* bits 28-31 used in rpmVerifyAttrs */

# Comes from C cource.  lib/rpmcli.h
VERIFY_ATTRS =   \
  (VERIFY_MD5 | VERIFY_SIZE | VERIFY_LINKTO | VERIFY_USER | VERIFY_GROUP | \
   VERIFY_MTIME | VERIFY_MODE | VERIFY_RDEV | VERIFY_CONTEXTS)

VERIFY_ALL =     \
  (VERIFY_ATTRS | VERIFY_FILES | VERIFY_DEPS | VERIFY_SCRIPT | VERIFY_DIGEST |\
   VERIFY_SIGNATURE | VERIFY_HDRCHK)


# Some masks for what checks to NOT do on these file types.
# The C code actiually resets these up for every file.
DIR_FLAGS = ~(RPMVERIFY_MD5 | RPMVERIFY_FILESIZE | RPMVERIFY_MTIME | \
              RPMVERIFY_LINKTO)

# These file types all have the same mask, but hopefully this will make the
# code more readable.
FIFO_FLAGS = CHR_FLAGS = BLK_FLAGS = GHOST_FLAGS = DIR_FLAGS

LINK_FLAGS = ~(RPMVERIFY_MD5 | RPMVERIFY_FILESIZE | RPMVERIFY_MTIME | \
               RPMVERIFY_MODE | RPMVERIFY_USER | RPMVERIFY_GROUP)

REG_FLAGS = ~(RPMVERIFY_LINKTO)


def s_isdev(mode):
    """
        Check to see if a file is a device.

    """
    return stat.S_ISBLK(mode) | stat.S_ISCHR(mode)

def rpmpackagelist(rts):
    """
        Equivalent of rpm -qa.  Intended for RefreshPackages() in the RPM Driver.
        Requires rpmtransactionset() to be run first to get a ts.
        Returns a list of pkgspec dicts.

        e.g. [ {'name':'foo', 'epoch':'20', 'version':'1.2', 'release':'5', 'arch':'x86_64' },
               {'name':'bar', 'epoch':'10', 'version':'5.2', 'release':'2', 'arch':'x86_64' } ]

    """
    return [{'name':header[rpm.RPMTAG_NAME],
             'epoch':header[rpm.RPMTAG_EPOCH],
             'version':header[rpm.RPMTAG_VERSION],
             'release':header[rpm.RPMTAG_RELEASE],
             'arch':header[rpm.RPMTAG_ARCH],
             'gpgkeyid':header.sprintf("%|SIGGPG?{%{SIGGPG:pgpsig}}:{None}|").split()[-1]}
             for header in rts.dbMatch()]

def getindexbykeyword(index_ts, **kwargs):
    """
        Return list of indexs from the rpmdb matching keywords
        ex: getHeadersByKeyword(name='foo', version='1', release='1')

        Can be passed any structure that can be indexed by the pkgspec
        keyswords as other keys are filtered out.

    """
    lst = []
    name = kwargs.get('name')
    if name:
        index_mi = index_ts.dbMatch(rpm.RPMTAG_NAME, name)
    else:
        index_mi = index_ts.dbMatch()

    if 'epoch' in kwargs:
        if kwargs['epoch'] != None and kwargs['epoch'] != 'None':
            kwargs['epoch'] = int(kwargs['epoch'])
        else:
            del(kwargs['epoch'])

    keywords = [key for key in list(kwargs.keys()) \
                         if key in ('name', 'epoch', 'version', 'release', 'arch')]
    keywords_len = len(keywords)
    for hdr in index_mi:
        match = 0
        for keyword in keywords:
            if hdr[keyword] == kwargs[keyword]:
                match += 1
        if match == keywords_len:
            lst.append(index_mi.instance())
    del index_mi
    return lst

def getheadersbykeyword(header_ts, **kwargs):
    """
        Borrowed parts of this from from Yum.  Need to fix it though.
        Epoch is not handled right.

        Return list of headers from the rpmdb matching keywords
        ex: getHeadersByKeyword(name='foo', version='1', release='1')

        Can be passed any structure that can be indexed by the pkgspec
        keyswords as other keys are filtered out.

    """
    lst = []
    name = kwargs.get('name')
    if name:
        header_mi = header_ts.dbMatch(rpm.RPMTAG_NAME, name)
    else:
        header_mi = header_ts.dbMatch()

    if 'epoch' in kwargs:
        if kwargs['epoch'] != None and kwargs['epoch'] != 'None':
            kwargs['epoch'] = int(kwargs['epoch'])
        else:
            del(kwargs['epoch'])

    keywords = [key for key in list(kwargs.keys()) \
                         if key in ('name', 'epoch', 'version', 'release', 'arch')]
    keywords_len = len(keywords)
    for hdr in header_mi:
        match = 0
        for keyword in keywords:
            if hdr[keyword] == kwargs[keyword]:
                match += 1
        if match == keywords_len:
            lst.append(hdr)
    del header_mi
    return lst

def prelink_md5_check(filename):
    """
        Checks if a file is prelinked.  If it is run it through prelink -y
        to get the unprelinked md5 and file size.

        Return 0 if the file was not prelinked, otherwise return the file size.
        Always return the md5.

    """
    prelink = False
    try:
        plf = open(filename, "rb")
    except IOError:
        return False, 0

    if prelink_exists:
        if isprelink_imported:
            plfd = plf.fileno()
            if isprelink(plfd):
                plf.close()
                cmd = '/usr/sbin/prelink -y %s 2> /dev/null' \
                                            % (re.escape(filename))
                plf = os.popen(cmd, 'rb')
                prelink = True
        elif whitelist_re.search(filename) and not blacklist_re.search(filename):
            plf.close()
            cmd = '/usr/sbin/prelink -y %s 2> /dev/null' \
                                        % (re.escape(filename))
            plf = os.popen(cmd, 'rb')
            prelink = True

    fsize = 0
    if py24compat:
        chksum = md5.new()
    else:
        chksum = hashlib.md5()
    while 1:
        data = plf.read()
        if not data:
            break
        fsize += len(data)
        chksum.update(data)
    plf.close()
    file_md5 = chksum.hexdigest()
    if prelink:
        return file_md5, fsize
    else:
        return file_md5, 0

def prelink_size_check(filename):
    """
       This check is only done if the prelink_md5_check() is not done first.

       Checks if a file is prelinked.  If it is run it through prelink -y
       to get the unprelinked file size.

       Return 0 if the file was not prelinked, otherwise return the file size.

    """
    fsize = 0
    try:
        plf = open(filename, "rb")
    except IOError:
        return False

    if prelink_exists:
        if isprelink_imported:
            plfd = plf.fileno()
            if isprelink(plfd):
                plf.close()
                cmd = '/usr/sbin/prelink -y %s 2> /dev/null' \
                                            % (re.escape(filename))
                plf = os.popen(cmd, 'rb')

                while 1:
                    data = plf.read()
                    if not data:
                        break
                    fsize += len(data)

        elif whitelist_re.search(filename) and not blacklist_re.search(filename):
            plf.close()
            cmd = '/usr/sbin/prelink -y %s 2> /dev/null' \
                                        % (re.escape(filename))
            plf = os.popen(cmd, 'rb')

            while 1:
                data = plf.read()
                if not data:
                    break
                fsize += len(data)

    plf.close()

    return fsize

def debug_verify_flags(vflags):
    """
        Decodes the verify flags bits.
    """
    if vflags & RPMVERIFY_MD5:
        print('RPMVERIFY_MD5')
    if vflags & RPMVERIFY_FILESIZE:
        print('RPMVERIFY_FILESIZE')
    if vflags & RPMVERIFY_LINKTO:
        print('RPMVERIFY_LINKTO')
    if vflags & RPMVERIFY_USER:
        print('RPMVERIFY_USER')
    if vflags & RPMVERIFY_GROUP:
        print('RPMVERIFY_GROUP')
    if vflags & RPMVERIFY_MTIME:
        print('RPMVERIFY_MTIME')
    if vflags & RPMVERIFY_MODE:
        print('RPMVERIFY_MODE')
    if vflags & RPMVERIFY_RDEV:
        print('RPMVERIFY_RDEV')
    if vflags & RPMVERIFY_CONTEXTS:
        print('RPMVERIFY_CONTEXTS')
    if vflags & RPMVERIFY_READLINKFAIL:
        print('RPMVERIFY_READLINKFAIL')
    if vflags & RPMVERIFY_READFAIL:
        print('RPMVERIFY_READFAIL')
    if vflags & RPMVERIFY_LSTATFAIL:
        print('RPMVERIFY_LSTATFAIL')
    if vflags & RPMVERIFY_LGETFILECONFAIL:
        print('RPMVERIFY_LGETFILECONFAIL')

def debug_file_flags(fflags):
    """
        Decodes the file flags bits.
    """
    if fflags & rpm.RPMFILE_CONFIG:
        print('rpm.RPMFILE_CONFIG')

    if fflags & rpm.RPMFILE_DOC:
        print('rpm.RPMFILE_DOC')

    if fflags & rpm.RPMFILE_ICON:
        print('rpm.RPMFILE_ICON')

    if fflags & rpm.RPMFILE_MISSINGOK:
        print('rpm.RPMFILE_MISSINGOK')

    if fflags & rpm.RPMFILE_NOREPLACE:
        print('rpm.RPMFILE_NOREPLACE')

    if fflags & rpm.RPMFILE_GHOST:
        print('rpm.RPMFILE_GHOST')

    if fflags & rpm.RPMFILE_LICENSE:
        print('rpm.RPMFILE_LICENSE')

    if fflags & rpm.RPMFILE_README:
        print('rpm.RPMFILE_README')

    if fflags & rpm.RPMFILE_EXCLUDE:
        print('rpm.RPMFILE_EXLUDE')

    if fflags & rpm.RPMFILE_UNPATCHED:
        print('rpm.RPMFILE_UNPATCHED')

    if fflags & rpm.RPMFILE_PUBKEY:
        print('rpm.RPMFILE_PUBKEY')

def rpm_verify_file(fileinfo, rpmlinktos, omitmask):
    """
        Verify all the files in a package.

        Returns a list of error flags, the file type and file name.  The list
        entries are strings that are the same as the labels for the bitwise
        flags used in the C code.

    """
    (fname, fsize, fmode, fmtime, fflags, frdev, finode, fnlink, fstate, \
            vflags, fuser, fgroup, fmd5) = fileinfo

    # 1. rpmtsRootDir stuff.  What does it do and where to I get it from?

    file_results = []
    flags = vflags

    # Check to see if the file was installed - if not pretend all is ok.
    # This is what the rpm C code does!
    if fstate != rpm.RPMFILE_STATE_NORMAL:
        return file_results

    # Get the installed files stats
    try:
        lstat = os.lstat(fname)
    except OSError:
        if not (fflags & (rpm.RPMFILE_MISSINGOK|rpm.RPMFILE_GHOST)):
            file_results.append('RPMVERIFY_LSTATFAIL')
            #file_results.append(fname)
        return file_results

    # 5. Contexts?  SELinux stuff?

    # Setup what checks to do.  This is straight out of the C code.
    if stat.S_ISDIR(lstat.st_mode):
        flags &= DIR_FLAGS
    elif stat.S_ISLNK(lstat.st_mode):
        flags &= LINK_FLAGS
    elif stat.S_ISFIFO(lstat.st_mode):
        flags &= FIFO_FLAGS
    elif stat.S_ISCHR(lstat.st_mode):
        flags &= CHR_FLAGS
    elif stat.S_ISBLK(lstat.st_mode):
        flags &= BLK_FLAGS
    else:
        flags &= REG_FLAGS

    if (fflags & rpm.RPMFILE_GHOST):
        flags &= GHOST_FLAGS

    flags &= ~(omitmask | RPMVERIFY_FAILURES)

    # 8. SELinux stuff.

    prelink_size = 0
    if flags & RPMVERIFY_MD5:
        prelink_md5, prelink_size = prelink_md5_check(fname)
        if prelink_md5 == False:
            file_results.append('RPMVERIFY_MD5')
            file_results.append('RPMVERIFY_READFAIL')
        elif  prelink_md5 != fmd5:
            file_results.append('RPMVERIFY_MD5')

    if flags & RPMVERIFY_LINKTO:
        linkto = os.readlink(fname)
        if not linkto:
            file_results.append('RPMVERIFY_READLINKFAIL')
            file_results.append('RPMVERIFY_LINKTO')
        else:
            if len(rpmlinktos) == 0  or linkto != rpmlinktos:
                file_results.append('RPMVERIFY_LINKTO')

    if flags & RPMVERIFY_FILESIZE:
        if not (flags & RPMVERIFY_MD5): # prelink check hasn't been done.
            prelink_size = prelink_size_check(fname)
        if (prelink_size != 0):         # This is a prelinked file.
            if (prelink_size != fsize):
                file_results.append('RPMVERIFY_FILESIZE')
        elif lstat.st_size != fsize:    # It wasn't a prelinked file.
            file_results.append('RPMVERIFY_FILESIZE')

    if flags & RPMVERIFY_MODE:
        metamode = fmode
        filemode = lstat.st_mode

        # Comparing the type of %ghost files is meaningless, but perms are ok.
        if fflags & rpm.RPMFILE_GHOST:
            metamode &= ~0xf000
            filemode &= ~0xf000

        if (stat.S_IFMT(metamode) != stat.S_IFMT(filemode)) or \
           (stat.S_IMODE(metamode) != stat.S_IMODE(filemode)):
            file_results.append('RPMVERIFY_MODE')

    if flags & RPMVERIFY_RDEV:
        if (stat.S_ISCHR(fmode) != stat.S_ISCHR(lstat.st_mode) or
            stat.S_ISBLK(fmode) != stat.S_ISBLK(lstat.st_mode)):
            file_results.append('RPMVERIFY_RDEV')
        elif (s_isdev(fmode) & s_isdev(lstat.st_mode)):
            st_rdev = lstat.st_rdev
            if frdev != st_rdev:
                file_results.append('RPMVERIFY_RDEV')

    if flags & RPMVERIFY_MTIME:
        if lstat.st_mtime != fmtime:
            file_results.append('RPMVERIFY_MTIME')

    if flags & RPMVERIFY_USER:
        try:
            user = pwd.getpwuid(lstat.st_uid)[0]
        except KeyError:
            user = None
        if not user or not fuser or (user != fuser):
            file_results.append('RPMVERIFY_USER')

    if flags & RPMVERIFY_GROUP:
        try:
            group = grp.getgrgid(lstat.st_gid)[0]
        except KeyError:
            group = None
        if not group or not fgroup or (group != fgroup):
            file_results.append('RPMVERIFY_GROUP')

    return file_results

def rpm_verify_dependencies(header):
    """
        Check package dependencies. Header is an rpm.hdr.

        Don't like opening another ts to do this, but
        it was the only way I could find of clearing the ts
        out.

        Have asked on the rpm-maint list on how to do
        this the right way (28 Feb 2007).

        ts.check() returns:

        ((name, version, release), (reqname, reqversion), \
            flags, suggest, sense)

    """
    _ts1 = rpmtransactionset()
    _ts1.addInstall(header, 'Dep Check', 'i')
    dep_errors = _ts1.check()
    _ts1.closeDB()
    return dep_errors

def rpm_verify_package(vp_ts, header, verify_options):
    """
        Verify a single package specified by header.  Header is an rpm.hdr.

        If errors are found it returns a dictionary of errors.

    """
    # Set some transaction level flags.
    vsflags = 0
    if 'nodigest' in verify_options:
        vsflags |= rpm._RPMVSF_NODIGESTS
    if 'nosignature' in verify_options:
        vsflags |= rpm._RPMVSF_NOSIGNATURES
    ovsflags = vp_ts.setVSFlags(vsflags)

    # Map from the Python options to the rpm bitwise flags.
    omitmask = 0

    if 'nolinkto' in verify_options:
        omitmask |= VERIFY_LINKTO
    if 'nomd5' in verify_options:
        omitmask |= VERIFY_MD5
    if 'nosize' in verify_options:
        omitmask |= VERIFY_SIZE
    if 'nouser' in verify_options:
        omitmask |= VERIFY_USER
    if 'nogroup' in verify_options:
        omitmask |= VERIFY_GROUP
    if 'nomtime' in verify_options:
        omitmask |= VERIFY_MTIME
    if 'nomode' in verify_options:
        omitmask |= VERIFY_MODE
    if 'nordev' in verify_options:
        omitmask |= VERIFY_RDEV

    omitmask = ((~omitmask & VERIFY_ATTRS) ^ VERIFY_ATTRS)

    package_results = {}

    # Check Signatures and Digests.
    # No idea what this might return.  Need to break something to see.
    # Setting the vsflags above determines what gets checked in the header.
    hdr_stat = vp_ts.hdrCheck(header.unload())
    if hdr_stat:
        package_results['hdr'] = hdr_stat

    # Check Package Depencies.
    if 'nodeps' not in verify_options:
        dep_stat = rpm_verify_dependencies(header)
        if dep_stat:
            package_results['deps'] = dep_stat

    # Check all the package files.
    if 'nofiles' not in verify_options:
        vp_fi = header.fiFromHeader()
        for fileinfo in vp_fi:
            # Do not bother doing anything with ghost files.
            # This is what RPM does.
            if fileinfo[4] & rpm.RPMFILE_GHOST:
                continue

            # This is only needed because of an inconsistency in the
            # rpm.fi interface.
            linktos = vp_fi.FLink()

            file_stat = rpm_verify_file(fileinfo, linktos, omitmask)

            #if len(file_stat) > 0 or options.verbose:
            if len(file_stat) > 0:
                fflags = fileinfo[4]
                if fflags & rpm.RPMFILE_CONFIG:
                    file_stat.append('c')
                elif fflags & rpm.RPMFILE_DOC:
                    file_stat.append('d')
                elif fflags & rpm.RPMFILE_GHOST:
                    file_stat.append('g')
                elif fflags & rpm.RPMFILE_LICENSE:
                    file_stat.append('l')
                elif fflags & rpm.RPMFILE_PUBKEY:
                    file_stat.append('P')
                elif fflags & rpm.RPMFILE_README:
                    file_stat.append('r')
                else:
                    file_stat.append(' ')

                file_stat.append(fileinfo[0]) # The filename.
                package_results.setdefault('files', []).append(file_stat)

    # Run the verify script if there is one.
    # Do we want this?
    #if 'noscripts' not in verify_options:
    #    script_stat = rpmVerifyscript()
    #    if script_stat:
    #        package_results['script'] = script_stat

    # If there have been any errors, add the package nevra to the result.
    if len(package_results) > 0:
        package_results.setdefault('nevra', (header[rpm.RPMTAG_NAME], \
                                             header[rpm.RPMTAG_EPOCH], \
                                             header[rpm.RPMTAG_VERSION], \
                                             header[rpm.RPMTAG_RELEASE], \
                                             header[rpm.RPMTAG_ARCH]))
    else:
        package_results = None

    # Put things back the way we found them.
    vsflags = vp_ts.setVSFlags(ovsflags)

    return package_results

def rpm_verify(verify_ts, verify_pkgspec, verify_options=[]):
    """
       Requires rpmtransactionset() to be run first to get a ts.

       pkgspec is a dict specifying the package
       e.g.:
           For a single package
           { name='foo', epoch='20', version='1', release='1', arch='x86_64'}

           For all packages
           {}

       Or any combination of keywords to select one or more packages to verify.

       options is a list of 'rpm --verify' options. Default is to check everything.
       e.g.:
           [ 'nodeps', 'nodigest', 'nofiles', 'noscripts', 'nosignature',
             'nolinkto' 'nomd5', 'nosize', 'nouser', 'nogroup', 'nomtime',
             'nomode', 'nordev' ]

       Returns a list.  One list entry per package.  Each list entry is a
       dictionary.  Dict keys are 'files', 'deps', 'nevra' and 'hdr'.
       Entries only get added for the failures. If nothing failed, None is
       returned.

       Its all a bit messy and probably needs reviewing.

       [ { 'hdr': [???],
           'deps: [((name, version, release), (reqname, reqversion),
                    flags, suggest, sense), .... ]
           'files': [ ['filename1', 'RPMVERIFY_GROUP', 'RPMVERIFY_USER' ],
                      ['filename2', 'RPMVERFIY_LSTATFAIL']]
           'nevra': ['name1', 'epoch1', 'version1', 'release1', 'arch1'] }
         { 'hdr': [???],
           'deps: [((name, version, release), (reqname, reqversion),
                    flags, suggest, sense), .... ]
           'files': [ ['filename', 'RPMVERIFY_GROUP', 'RPMVERIFY_USER" ],
                      ['filename2', 'RPMVERFIY_LSTATFAIL']]
           'nevra': ['name2', 'epoch2', 'version2', 'release2', 'arch2'] } ]

    """
    verify_results = []
    headers = getheadersbykeyword(verify_ts, **verify_pkgspec)
    for header in headers:
        result = rpm_verify_package(verify_ts, header, verify_options)
        if result:
            verify_results.append(result)

    return verify_results

def rpmtransactionset():
    """
        A simple wrapper for rpm.TransactionSet() to keep everthiing together.
        Might use it to set some ts level flags later.

    """
    ts = rpm.TransactionSet()
    return ts

class Rpmtscallback(object):
    """
        Callback for ts.run().  Used for adding, upgrading and removing packages.
        Starting with all possible reasons codes, but bcfg2 will probably only
        make use of a few of them.

        Mostly just printing stuff at the moment to understand how the callback
        is used.

    """
    def __init__(self):
        self.fdnos = {}

    def callback(self, reason, amount, total, key, client_data):
        """
            Generic rpmts call back.
        """
        if   reason == rpm.RPMCALLBACK_INST_OPEN_FILE:
            pass
        elif reason == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            pass
        elif reason == rpm.RPMCALLBACK_INST_START:
            pass
        elif reason == rpm.RPMCALLBACK_TRANS_PROGRESS or \
             reason == rpm.RPMCALLBACK_INST_PROGRESS:
            pass
            #       rpm.RPMCALLBACK_INST_PROGRESS'
        elif reason == rpm.RPMCALLBACK_TRANS_START:
            pass
        elif reason == rpm.RPMCALLBACK_TRANS_STOP:
            pass
        elif reason == rpm.RPMCALLBACK_REPACKAGE_START:
            pass
        elif reason == rpm.RPMCALLBACK_REPACKAGE_PROGRESS:
            pass
        elif reason == rpm.RPMCALLBACK_REPACKAGE_STOP:
            pass
        elif reason == rpm.RPMCALLBACK_UNINST_PROGRESS:
            pass
        elif reason == rpm.RPMCALLBACK_UNINST_START:
            pass
        elif reason == rpm.RPMCALLBACK_UNINST_STOP:
            pass
            # How do we get at this?
            # RPM.modified += key
        elif reason == rpm.RPMCALLBACK_UNPACK_ERROR:
            pass
        elif reason == rpm.RPMCALLBACK_CPIO_ERROR:
            pass
        elif reason == rpm.RPMCALLBACK_UNKNOWN:
            pass
        else:
            print('ERROR - Fell through callBack')


def rpm_erase(erase_pkgspecs, erase_flags):
    """
       pkgspecs is a list of pkgspec dicts specifying packages
       e.g.:
           For a single package
           { name='foo', epoch='20', version='1', release='1', arch='x86_64'}

    """
    erase_ts_flags = 0
    if 'noscripts' in erase_flags:
        erase_ts_flags |= rpm.RPMTRANS_FLAG_NOSCRIPTS
    if 'notriggers' in erase_flags:
        erase_ts_flags |= rpm.RPMTRANS_FLAG_NOTRIGGERS
    if 'repackage' in erase_flags:
        erase_ts_flags |= rpm.RPMTRANS_FLAG_REPACKAGE

    erase_ts = rpmtransactionset()
    erase_ts.setFlags(erase_ts_flags)

    for pkgspec in erase_pkgspecs:
        idx_list = getindexbykeyword(erase_ts, **pkgspec)
        if len(idx_list) > 1 and not 'allmatches' in erase_flags:
            #pass
            print('ERROR - Multiple package match for erase', pkgspec)
        else:
            for idx in idx_list:
                erase_ts.addErase(idx)

    #for te in erase_ts:

    erase_problems = []
    if 'nodeps' not in erase_flags:
        erase_problems = erase_ts.check()

    if erase_problems == []:
        erase_ts.order()
        erase_callback = Rpmtscallback()
        erase_ts.run(erase_callback.callback, 'Erase')
    #else:

    erase_ts.closeDB()
    del erase_ts
    return erase_problems

def display_verify_file(file_results):
    '''
        Display file results similar to rpm --verify.
    '''
    filename = file_results[-1]
    filetype = file_results[-2]

    result_string = ''

    if 'RPMVERIFY_LSTATFAIL' in file_results:
        result_string = 'missing '
    else:
        if 'RPMVERIFY_FILESIZE' in file_results:
            result_string = result_string + 'S'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_MODE' in file_results:
            result_string = result_string + 'M'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_MD5' in file_results:
            if 'RPMVERIFY_READFAIL' in file_results:
                result_string = result_string + '?'
            else:
                result_string = result_string + '5'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_RDEV' in file_results:
            result_string = result_string + 'D'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_LINKTO' in file_results:
            if 'RPMVERIFY_READLINKFAIL' in file_results:
                result_string = result_string + '?'
            else:
                result_string = result_string + 'L'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_USER' in file_results:
            result_string = result_string + 'U'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_GROUP' in file_results:
            result_string = result_string + 'G'
        else:
            result_string = result_string + '.'

        if 'RPMVERIFY_MTIME' in file_results:
            result_string = result_string + 'T'
        else:
            result_string = result_string + '.'

    print(result_string + '  ' + filetype + ' ' + filename)
    sys.stdout.flush()

#===============================================================================
# Some options and output to assist with development and testing.
# These are not intended for normal use.
if __name__ == "__main__":

    p = optparse.OptionParser()

    p.add_option('--name', action='store', \
                 default=None, \
                 help='''Package name to verify.

                         ******************************************
                         NOT SPECIFYING A NAME MEANS 'ALL' PACKAGES.
                         ******************************************

                         The specified operation will be carried out on  all
                         instances of packages that match the package specification
                         (name, epoch, version, release, arch).''')

    p.add_option('--epoch', action='store', \
                 default=None, \
                 help='''Package epoch.''')

    p.add_option('--version', action='store', \
                 default=None, \
                 help='''Package version.''')

    p.add_option('--release', action='store', \
                 default=None, \
                 help='''Package release.''')

    p.add_option('--arch', action='store', \
                 default=None, \
                 help='''Package arch.''')

    p.add_option('--erase', '-e', action='store_true', \
                 default=None, \
                 help='''****************************************************
                         REMOVE PACKAGES.  THERE ARE NO WARNINGS.  MULTIPLE
                         PACKAGES WILL BE REMOVED IF A FULL PACKAGE SPEC IS NOT
                         GIVEN. E.G. IF JUST A NAME IS GIVEN ALL INSTALLED
                         INSTANCES OF THAT PACKAGE WILL BE REMOVED PROVIDED
                         DEPENDENCY CHECKS PASS.  IF JUST AN EPOCH IS GIVEN
                         ALL PACKAGE INSTANCES WITH THAT EPOCH WILL BE REMOVED.
                         ****************************************************''')

    p.add_option('--list', '-l', action='store_true', \
                 help='''List package identity info. rpm -qa ish equivalent
                         intended for use in RefreshPackages().''')

    p.add_option('--verify', action='store_true', \
                 help='''Verify Package(s).  Output is only produced after all
                         packages has been verified. Be patient.''')

    p.add_option('--verbose', '-v', action='store_true', \
                 help='''Verbose output for --verify option.  Output is the
                         same as rpm -v --verify.''')

    p.add_option('--nodeps', action='store_true', \
                 default=False, \
                 help='Do not do dependency testing.')

    p.add_option('--nodigest', action='store_true', \
                 help='Do not check package digests.')

    p.add_option('--nofiles', action='store_true', \
                 help='Do not do file checks.')

    p.add_option('--noscripts', action='store_true', \
                 help='Do not run verification scripts.')

    p.add_option('--nosignature', action='store_true', \
                 help='Do not do package signature verification.')

    p.add_option('--nolinkto', action='store_true', \
                 help='Do not do symlink tests.')

    p.add_option('--nomd5', action='store_true', \
                 help='''Do not do MD5 checksums on files.  Note that this does
                                            not work for prelink files yet.''')

    p.add_option('--nosize', action='store_true', \
                 help='''Do not do file size tests. Note that this does not work
                                            for prelink files yet.''')

    p.add_option('--nouser', action='store_true', \
                 help='Do not check file user ownership.')

    p.add_option('--nogroup', action='store_true', \
                 help='Do not check file group ownership.')

    p.add_option('--nomtime', action='store_true', \
                 help='Do not check file modification times.')

    p.add_option('--nomode', action='store_true', \
                 help='Do not check file modes (permissions).')

    p.add_option('--nordev', action='store_true', \
                 help='Do not check device node.')

    p.add_option('--notriggers', action='store_true', \
                 help='Do not do not generate triggers on erase.')

    p.add_option('--repackage', action='store_true', \
                 help='''Do repackage on erase.i Packages are put
                                            in /var/spool/repackage.''')

    p.add_option('--allmatches', action='store_true', \
                 help='''Remove all package instances that match the
                         pkgspec.

                         ***************************************************
                         NO WARNINGS ARE GIVEN.  IF THERE IS NO PACKAGE SPEC
                         THAT MEANS ALL PACKAGES!!!!
                         ***************************************************''')

    options, arguments = p.parse_args()

    pkgspec = {}
    rpm_options = []

    if options.nodeps:
        rpm_options.append('nodeps')

    if options.nodigest:
        rpm_options.append('nodigest')

    if options.nofiles:
        rpm_options.append('nofiles')

    if options.noscripts:
        rpm_options.append('noscripts')

    if options.nosignature:
        rpm_options.append('nosignature')

    if options.nolinkto:
        rpm_options.append('nolinkto')

    if options.nomd5:
        rpm_options.append('nomd5')

    if options.nosize:
        rpm_options.append('nosize')

    if options.nouser:
        rpm_options.append('nouser')

    if options.nogroup:
        rpm_options.append('nogroup')

    if options.nomtime:
        rpm_options.append('nomtime')

    if options.nomode:
        rpm_options.append('nomode')

    if options.nordev:
        rpm_options.append('nordev')

    if options.repackage:
        rpm_options.append('repackage')

    if options.allmatches:
        rpm_options.append('allmatches')

    main_ts = rpmtransactionset()

    cmdline_pkgspec = {}
    if options.name != 'all':
        if options.name:
            cmdline_pkgspec['name'] = str(options.name)
        if options.epoch:
            cmdline_pkgspec['epoch'] = str(options.epoch)
        if options.version:
            cmdline_pkgspec['version'] = str(options.version)
        if options.release:
            cmdline_pkgspec['release'] = str(options.release)
        if options.arch:
            cmdline_pkgspec['arch'] = str(options.arch)

    if options.verify:
        results = rpm_verify(main_ts, cmdline_pkgspec, rpm_options)
        for r in results:
            files = r.get('files', '')
            for f in files:
                display_verify_file(f)

    elif options.list:
        for p in rpmpackagelist(main_ts):
            print(p)

    elif options.erase:
        if options.name:
            rpm_erase([cmdline_pkgspec], rpm_options)
        else:
            print('You must specify the "--name" option')


class RPM(Bcfg2.Client.Tools.PkgTool):
    """Support for RPM packages."""
    options = Bcfg2.Client.Tools.PkgTool.options + [
        Bcfg2.Options.Option(
            cf=('RPM', 'installonlypackages'), dest="rpm_installonly",
            type=Bcfg2.Options.Types.comma_list,
            default=['kernel', 'kernel-bigmem', 'kernel-enterprise',
                     'kernel-smp', 'kernel-modules', 'kernel-debug',
                     'kernel-unsupported', 'kernel-devel', 'kernel-source',
                     'kernel-default', 'kernel-largesmp-devel',
                     'kernel-largesmp', 'kernel-xen', 'gpg-pubkey'],
            help='RPM install-only packages'),
        Bcfg2.Options.BooleanOption(
            cf=('RPM', 'pkg_checks'), default=True, dest="rpm_pkg_checks",
            help="Perform RPM package checks"),
        Bcfg2.Options.BooleanOption(
            cf=('RPM', 'pkg_verify'), default=True, dest="rpm_pkg_verify",
            help="Perform RPM package verify"),
        Bcfg2.Options.BooleanOption(
            cf=('RPM', 'install_missing'), default=True,
            dest="rpm_install_missing",
            help="Install missing packages"),
        Bcfg2.Options.Option(
            cf=('RPM', 'erase_flags'), default=["allmatches"],
            dest="rpm_erase_flags",
            help="RPM erase flags"),
        Bcfg2.Options.BooleanOption(
            cf=('RPM', 'fix_version'), default=True,
            dest="rpm_fix_version",
            help="Fix (upgrade or downgrade) packages with the wrong version"),
        Bcfg2.Options.BooleanOption(
            cf=('RPM', 'reinstall_broken'), default=True,
            dest="rpm_reinstall_broken",
            help="Reinstall packages that fail to verify"),
        Bcfg2.Options.Option(
            cf=('RPM', 'verify_flags'), default=[], dest="rpm_verify_flags",
            help="RPM verify flags")]

    __execs__ = ['/bin/rpm', '/var/lib/rpm']
    __handles__ = [('Package', 'rpm')]

    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['url']}

    __new_req__ = {'Package': ['name'],
                   'Instance': ['version', 'release', 'arch']}
    __new_ireq__ = {'Package': ['uri'], \
                    'Instance': ['simplefile']}

    __gpg_req__ = {'Package': ['name', 'version']}
    __gpg_ireq__ = {'Package': ['name', 'version']}

    __new_gpg_req__ = {'Package': ['name'],
                       'Instance': ['version', 'release']}
    __new_gpg_ireq__ = {'Package': ['name'],
                        'Instance': ['version', 'release']}

    pkgtype = 'rpm'
    pkgtool = ("rpm --oldpackage --replacepkgs --quiet -U %s", ("%s", ["url"]))

    def __init__(self, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, config)

        # create a global ignore list used when ignoring particular
        # files during package verification
        self.ignores = [entry.get('name') for struct in config for entry in struct \
                        if entry.get('type') == 'ignore']
        self.instance_status = {}
        self.extra_instances = []
        self.modlists = {}
        self.gpg_keyids = self.getinstalledgpg()

        self.installOnlyPkgs = Bcfg2.Options.setup.rpm_installonly
        if 'gpg-pubkey' not in self.installOnlyPkgs:
            self.installOnlyPkgs.append('gpg-pubkey')
        self.verify_flags = Bcfg2.Options.setup.rpm_verify_flags
        if '' in self.verify_flags:
            self.verify_flags.remove('')

        self.logger.debug('%s: installOnlyPackages = %s' %
                          (self.name, self.installOnlyPkgs))
        self.logger.debug('%s: erase_flags = %s' %
                          (self.name, Bcfg2.Options.setup.rpm_erase_flags))
        self.logger.debug('%s: pkg_checks = %s' %
                          (self.name, Bcfg2.Options.setup.rpm_pkg_checks))
        self.logger.debug('%s: pkg_verify = %s' %
                          (self.name, Bcfg2.Options.setup.rpm_pkg_verify))
        self.logger.debug('%s: install_missing = %s' %
                          (self.name, Bcfg2.Options.setup.install_missing))
        self.logger.debug('%s: fix_version = %s' %
                          (self.name, Bcfg2.Options.setup.rpm_fix_version))
        self.logger.debug('%s: reinstall_broken = %s' %
                          (self.name,
                           Bcfg2.Options.setup.rpm_reinstall_broken))
        self.logger.debug('%s: verify_flags = %s' %
                          (self.name, self.verify_flags))

        # Force a re- prelink of all packages if prelink exists.
        # Many, if not most package verifies can be caused by out of
        # date prelinking.
        if (os.path.isfile('/usr/sbin/prelink') and
            not Bcfg2.Options.setup.dry_run):
            rv = self.cmd.run('/usr/sbin/prelink -a -mR')
            if rv.success:
                self.logger.debug('Pre-emptive prelink succeeded')
            else:
                # FIXME : this is dumb - what if the output is huge?
                self.logger.error('Pre-emptive prelink failed: %s' % rv.error)

    def RefreshPackages(self):
        """
            Creates self.installed{} which is a dict of installed packages.

            The dict items are lists of nevra dicts.  This loosely matches the
            config from the server and what rpmtools uses to specify pacakges.

            e.g.

            self.installed['foo'] = [ {'name':'foo', 'epoch':None,
                                       'version':'1', 'release':2,
                                       'arch':'i386'},
                                      {'name':'foo', 'epoch':None,
                                       'version':'1', 'release':2,
                                       'arch':'x86_64'} ]
        """
        self.installed = {}
        refresh_ts = rpmtransactionset()
        # Don't bother with signature checks at this stage. The GPG keys might
        # not be installed.
        refresh_ts.setVSFlags(rpm._RPMVSF_NODIGESTS|rpm._RPMVSF_NOSIGNATURES)
        for nevra in rpmpackagelist(refresh_ts):
            self.installed.setdefault(nevra['name'], []).append(nevra)
        if Bcfg2.Options.setup.debug:
            print("The following package instances are installed:")
            for name, instances in list(self.installed.items()):
                self.logger.debug("    " + name)
                for inst in instances:
                    self.logger.debug("        %s" %self.str_evra(inst))
        refresh_ts.closeDB()
        del refresh_ts

    def VerifyPackage(self, entry, modlist, pinned_version=None):
        """
            Verify Package status for entry.
            Performs the following:
                - Checks for the presence of required Package Instances.
                - Compares the evra 'version' info against self.installed{}.
                - RPM level package verify (rpm --verify).
                - Checks for the presence of unrequired package instances.

            Produces the following dict and list for RPM.Install() to use:
              For installs/upgrades/fixes of required instances:
                instance_status = { <Instance Element Object>:
                                       { 'installed': True|False,
                                         'version_fail': True|False,
                                         'verify_fail': True|False,
                                         'pkg': <Package Element Object>,
                                         'modlist': [ <filename>, ... ],
                                         'verify' : [ <rpm --verify results> ]
                                       }, ......
                                  }

              For deletions of unrequired instances:
                extra_instances = [ <Package Element Object>, ..... ]

              Constructs the text prompts for interactive mode.
        """
        instances = [inst for inst in entry if inst.tag == 'Instance' or inst.tag == 'Package']
        if instances == []:
            # We have an old style no Instance entry. Convert it to new style.
            instance = Bcfg2.Client.XML.SubElement(entry, 'Package')
            for attrib in list(entry.attrib.keys()):
                instance.attrib[attrib] = entry.attrib[attrib]
            if (Bcfg2.Options.setup.rpm_pkg_checks and
                entry.get('pkg_checks', 'true').lower() == 'true'):
                if 'any' in [entry.get('version'), pinned_version]:
                    version, release = 'any', 'any'
                elif entry.get('version') == 'auto':
                    if pinned_version != None:
                        version, release = pinned_version.split('-')
                    else:
                        return False
                else:
                    version, release = entry.get('version').split('-')
                instance.set('version', version)
                instance.set('release', release)
                if entry.get('verify', 'true') == 'false':
                    instance.set('verify', 'false')
            instances = [ instance ]

        self.logger.debug("Verifying package instances for %s" % entry.get('name'))
        package_fail = False
        qtext_versions = ''

        if entry.get('name') in self.installed:
            # There is at least one instance installed.
            if (Bcfg2.Options.setup.rpm_pkg_checks and
                entry.get('pkg_checks', 'true').lower() == 'true'):
                rpmTs = rpm.TransactionSet()
                rpmHeader = None
                for h in rpmTs.dbMatch(rpm.RPMTAG_NAME, entry.get('name')):
                    if rpmHeader is None or rpm.versionCompare(h, rpmHeader) > 0:
                        rpmHeader = h
                rpmProvides = [ h['provides'] for h in \
                            rpmTs.dbMatch(rpm.RPMTAG_NAME, entry.get('name')) ]
                rpmIntersection = set(rpmHeader['provides']) & \
                                  set(self.installOnlyPkgs)
                if len(rpmIntersection) > 0:
                    # Packages that should only be installed or removed.
                    # e.g. kernels.
                    self.logger.debug("        Install only package.")
                    for inst in instances:
                        self.instance_status.setdefault(inst, {})['installed'] = False
                        self.instance_status[inst]['version_fail'] = False
                        if inst.tag == 'Package' and len(self.installed[entry.get('name')]) > 1:
                            self.logger.error("WARNING: Multiple instances of package %s are installed." % \
                                              (entry.get('name')))
                        for pkg in self.installed[entry.get('name')]:
                            if inst.get('version') == 'any' or self.pkg_vr_equal(inst, pkg) \
                               or self.inst_evra_equal(inst, pkg):
                                if inst.get('version') == 'any':
                                    self.logger.error("got any version")
                                self.logger.debug("        %s" % self.str_evra(inst))
                                self.instance_status[inst]['installed'] = True

                                if (Bcfg2.Options.setup.rpm_pkg_verify and
                                    inst.get('pkg_verify', 'true').lower() == 'true'):
                                    flags = inst.get('verify_flags', '').split(',') + self.verify_flags
                                    if pkg.get('gpgkeyid', '')[-8:] not in self.gpg_keyids and \
                                       entry.get('name') != 'gpg-pubkey':
                                        flags += ['nosignature', 'nodigest']
                                        self.logger.debug('WARNING: Package %s %s requires GPG Public key with ID %s'\
                                                           % (pkg.get('name'), self.str_evra(pkg), \
                                                              pkg.get('gpgkeyid', '')))
                                        self.logger.debug('         Disabling signature check.')

                                    if Bcfg2.Options.setup.quick:
                                        if prelink_exists:
                                            flags += ['nomd5', 'nosize']
                                        else:
                                            flags += ['nomd5']
                                    self.logger.debug("        verify_flags = %s" % flags)

                                    if inst.get('verify', 'true') == 'false':
                                        self.instance_status[inst]['verify'] = None
                                    else:
                                        vp_ts = rpmtransactionset()
                                        self.instance_status[inst]['verify'] = \
                                                                             rpm_verify( vp_ts, pkg, flags)
                                        vp_ts.closeDB()
                                        del vp_ts

                        if self.instance_status[inst]['installed'] == False:
                            self.logger.info("        Package %s %s not installed." % \
                                         (entry.get('name'), self.str_evra(inst)))

                            qtext_versions = qtext_versions + 'I(%s) ' % self.str_evra(inst)
                            entry.set('current_exists', 'false')
                else:
                    # Normal Packages that can be upgraded.
                    for inst in instances:
                        self.instance_status.setdefault(inst, {})['installed'] = False
                        self.instance_status[inst]['version_fail'] = False

                        # Only installed packages with the same architecture are
                        # relevant.
                        if inst.get('arch', None) == None:
                            arch_match = self.installed[entry.get('name')]
                        else:
                            arch_match = [pkg for pkg in self.installed[entry.get('name')] \
                                              if pkg.get('arch', None) == inst.get('arch', None)]

                        if len(arch_match) > 1:
                            self.logger.error("Multiple instances of package %s installed with the same achitecture." % \
                                                  (entry.get('name')))
                        elif len(arch_match) == 1:
                            # There is only one installed like there should be.
                            # Check that it is the right version.
                            for pkg in arch_match:
                                if inst.get('version') == 'any' or self.pkg_vr_equal(inst, pkg) or \
                                       self.inst_evra_equal(inst, pkg):
                                    self.logger.debug("        %s" % self.str_evra(inst))
                                    self.instance_status[inst]['installed'] = True

                                    if (Bcfg2.Options.setup.rpm_pkg_verify and
                                        inst.get('pkg_verify', 'true').lower() == 'true'):
                                        flags = inst.get('verify_flags', '').split(',') + self.verify_flags
                                        if pkg.get('gpgkeyid', '')[-8:] not in self.gpg_keyids and \
                                           'nosignature' not in flags:
                                            flags += ['nosignature', 'nodigest']
                                            self.logger.info('WARNING: Package %s %s requires GPG Public key with ID %s'\
                                                         % (pkg.get('name'), self.str_evra(pkg), \
                                                            pkg.get('gpgkeyid', '')))
                                            self.logger.info('         Disabling signature check.')

                                        if Bcfg2.Options.setup.quick:
                                            if prelink_exists:
                                                flags += ['nomd5', 'nosize']
                                            else:
                                                flags += ['nomd5']
                                        self.logger.debug("        verify_flags = %s" % flags)

                                        if inst.get('verify', 'true') == 'false':
                                            self.instance_status[inst]['verify'] = None
                                        else:
                                            vp_ts = rpmtransactionset()
                                            self.instance_status[inst]['verify'] = \
                                                                                 rpm_verify( vp_ts, pkg, flags )
                                            vp_ts.closeDB()
                                            del vp_ts

                                else:
                                    # Wrong version installed.
                                    self.instance_status[inst]['version_fail'] = True
                                    self.logger.info("        Wrong version installed.  Want %s, but have %s"\
                                                    % (self.str_evra(inst), self.str_evra(pkg)))

                                    qtext_versions = qtext_versions + 'U(%s -> %s) ' % \
                                                          (self.str_evra(pkg), self.str_evra(inst))
                        elif len(arch_match) == 0:
                            # This instance is not installed.
                            self.instance_status[inst]['installed'] = False
                            self.logger.info("        %s is not installed." % self.str_evra(inst))
                            qtext_versions = qtext_versions + 'I(%s) ' % self.str_evra(inst)

                # Check the rpm verify results.
                for inst in instances:
                    instance_fail = False
                    # Dump the rpm verify results.
                    #****Write something to format this nicely.*****
                    if (Bcfg2.Options.setup.debug and
                        self.instance_status[inst].get('verify', None)):
                        self.logger.debug(self.instance_status[inst]['verify'])

                    self.instance_status[inst]['verify_fail'] = False
                    if self.instance_status[inst].get('verify', None):
                        if len(self.instance_status[inst].get('verify')) > 1:
                            self.logger.info("WARNING: Verification of more than one package instance.")

                        for result in self.instance_status[inst]['verify']:

                            # Check header results
                            if result.get('hdr', None):
                                instance_fail = True
                                self.instance_status[inst]['verify_fail'] = True

                            # Check dependency results
                            if result.get('deps', None):
                                instance_fail = True
                                self.instance_status[inst]['verify_fail'] = True

                            # Check the rpm verify file results against the modlist
                            # and entry and per Instance Ignores.
                            ignores = [ig.get('name') for ig in entry.findall('Ignore')] + \
                                      [ig.get('name') for ig in inst.findall('Ignore')] + \
                                      self.ignores
                            for file_result in result.get('files', []):
                                if file_result[-1] not in modlist + ignores:
                                    instance_fail = True
                                    self.instance_status[inst]['verify_fail'] = True
                                else:
                                    self.logger.debug("        Modlist/Ignore match: %s" % \
                                                                                 (file_result[-1]))

                        if instance_fail == True:
                            self.logger.debug("*** Instance %s failed RPM verification ***" % \
                                              self.str_evra(inst))
                            qtext_versions = qtext_versions + 'R(%s) ' % self.str_evra(inst)
                            self.modlists[entry] = modlist

                            # Attach status structure for return to server for reporting.
                            inst.set('verify_status', str(self.instance_status[inst]))

                    if self.instance_status[inst]['installed'] == False or \
                       self.instance_status[inst].get('version_fail', False)== True or \
                       self.instance_status[inst].get('verify_fail', False) == True:
                        package_fail = True
                        self.instance_status[inst]['pkg'] = entry
                        self.modlists[entry] = modlist

                # Find Installed Instances that are not in the Config.
                extra_installed = self.FindExtraInstances(entry, self.installed[entry.get('name')])
                if extra_installed != None:
                    package_fail = True
                    self.extra_instances.append(extra_installed)
                    for inst in extra_installed.findall('Instance'):
                        qtext_versions = qtext_versions + 'D(%s) ' % self.str_evra(inst)
                    self.logger.debug("Found Extra Instances %s" % qtext_versions)

                if package_fail == True:
                    self.logger.info("        Package %s failed verification." % \
                                                              (entry.get('name')))
                    qtext = 'Install/Upgrade/delete Package %s instance(s) - %s (y/N) ' % \
                                                  (entry.get('name'), qtext_versions)
                    entry.set('qtext', qtext)

                    bcfg2_versions = ''
                    for bcfg2_inst in [inst for inst in instances if inst.tag == 'Instance']:
                        bcfg2_versions = bcfg2_versions + '(%s) ' % self.str_evra(bcfg2_inst)
                    if bcfg2_versions != '':
                        entry.set('version', bcfg2_versions)
                    installed_versions = ''

                    for installed_inst in self.installed[entry.get('name')]:
                        installed_versions = installed_versions + '(%s) ' % \
                                                                      self.str_evra(installed_inst)

                    entry.set('current_version', installed_versions)
                    return False

        else:
            # There are no Instances of this package installed.
            self.logger.debug("Package %s has no instances installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            bcfg2_versions = ''
            for inst in instances:
                qtext_versions = qtext_versions + 'I(%s) ' % self.str_evra(inst)
                self.instance_status.setdefault(inst, {})['installed'] = False
                self.modlists[entry] = modlist
                self.instance_status[inst]['pkg'] = entry
                if inst.tag == 'Instance':
                    bcfg2_versions = bcfg2_versions + '(%s) ' % self.str_evra(inst)
            if bcfg2_versions != '':
                entry.set('version', bcfg2_versions)
            entry.set('qtext', "Install Package %s Instance(s) %s? (y/N) " % \
                      (entry.get('name'), qtext_versions))

            return False
        return True

    def Remove(self, packages):
        """
           Remove specified entries.

           packages is a list of Package Entries with Instances generated
           by FindExtra().

        """
        self.logger.debug('Running RPM.Remove()')

        pkgspec_list = []
        for pkg in packages:
            for inst in pkg:
                if pkg.get('name') != 'gpg-pubkey':
                    pkgspec = { 'name':pkg.get('name'),
                            'epoch':inst.get('epoch', None),
                            'version':inst.get('version'),
                            'release':inst.get('release'),
                            'arch':inst.get('arch') }
                    pkgspec_list.append(pkgspec)
                else:
                    pkgspec = { 'name':pkg.get('name'),
                            'version':inst.get('version'),
                            'release':inst.get('release')}
                    self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                 % (pkgspec.get('name'), self.str_evra(pkgspec)))
                    self.logger.info("         This package will be deleted in a future version of the RPM driver.")
                #pkgspec_list.append(pkg_spec)

        erase_results = rpm_erase(pkgspec_list, Bcfg2.Options.setup.rpm_erase_flags)
        if erase_results == []:
            self.modified += packages
            for pkg in pkgspec_list:
                self.logger.info("Deleted %s %s" % (pkg.get('name'), self.str_evra(pkg)))
        else:
            self.logger.info("Bulk erase failed with errors:")
            self.logger.debug("Erase results = %s" % erase_results)
            self.logger.info("Attempting individual erase for each package.")
            pkgspec_list = []
            for pkg in packages:
                pkg_modified = False
                for inst in pkg:
                    if pkg.get('name') != 'gpg-pubkey':
                        pkgspec = { 'name':pkg.get('name'),
                                'epoch':inst.get('epoch', None),
                                'version':inst.get('version'),
                                'release':inst.get('release'),
                                'arch':inst.get('arch') }
                        pkgspec_list.append(pkgspec)
                    else:
                        pkgspec = { 'name':pkg.get('name'),
                                'version':inst.get('version'),
                                'release':inst.get('release')}
                        self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                   % (pkgspec.get('name'), self.str_evra(pkgspec)))
                        self.logger.info("         This package will be deleted in a future version of the RPM driver.")
                        continue # Don't delete the gpg-pubkey packages for now.
                    erase_results = rpm_erase(
                        [pkgspec],
                        Bcfg2.Options.setup.rpm_erase_flags)
                    if erase_results == []:
                        pkg_modified = True
                        self.logger.info("Deleted %s %s" % \
                                                   (pkgspec.get('name'), self.str_evra(pkgspec)))
                    else:
                        self.logger.error("unable to delete %s %s" % \
                                                   (pkgspec.get('name'), self.str_evra(pkgspec)))
                        self.logger.debug("Failure = %s" % erase_results)
                if pkg_modified == True:
                    self.modified.append(pkg)

        self.RefreshPackages()
        self.extra = self.FindExtra()

    def FixInstance(self, instance, inst_status):
        """
           Control if a reinstall of a package happens or not based on the
           results from RPM.VerifyPackage().

           Return True to reinstall, False to not reintstall.

        """
        fix = False

        if not inst_status.get('installed', False):
            if (instance.get('install_missing', 'true').lower() == "true" and
                Bcfg2.Options.setup.rpm_install_missing):
                fix = True
            else:
                self.logger.debug('Installed Action for %s %s is to not install' % \
                                  (inst_status.get('pkg').get('name'),
                                   self.str_evra(instance)))

        elif inst_status.get('version_fail', False):
            if (instance.get('fix_version', 'true').lower() == "true" and
                Bcfg2.Options.setup.rpm_fix_version):
                fix = True
            else:
                self.logger.debug('Version Fail Action for %s %s is to not upgrade' % \
                                  (inst_status.get('pkg').get('name'),
                                   self.str_evra(instance)))

        elif inst_status.get('verify_fail', False):
            if (instance.get('reinstall_broken', 'true').lower() == "true" and
                Bcfg2.Options.setup.rpm_reinstall_broken):
                for inst in inst_status.get('verify'):
                    # This needs to be a for loop rather than a straight get()
                    # because the underlying routines handle multiple packages
                    # and return a list of results.
                    self.logger.debug('reinstall_check: %s %s:%s-%s.%s' % inst.get('nevra'))

                    if inst.get("hdr", False):
                        fix = True

                    elif inst.get('files', False):
                        # Parse rpm verify file results
                        for file_result in inst.get('files', []):
                            self.logger.debug('reinstall_check: file: %s' % file_result)
                            if file_result[-2] != 'c':
                                fix = True
                                break

                    # Shouldn't really need this, but included for clarity.
                    elif inst.get("deps", False):
                        fix = False
            else:
                self.logger.debug('Verify Fail Action for %s %s is to not reinstall' % \
                                                     (inst_status.get('pkg').get('name'),
                                                      self.str_evra(instance)))

        return fix

    def Install(self, packages):
        """
           Try and fix everything that RPM.VerifyPackages() found wrong for
           each Package Entry.  This can result in individual RPMs being
           installed (for the first time), reinstalled, deleted, downgraded
           or upgraded.

           packages is a list of Package Elements that has
               states[<Package Element>] == False

           The following effects occur:
           - states{} is conditionally updated for each package.
           - self.installed{} is rebuilt, possibly multiple times.
           - self.instance_statusi{} is conditionally updated for each instance
             of a package.
           - Each package will be added to self.modified[] if its states{}
             entry is set to True.

        """
        self.logger.info('Runing RPM.Install()')

        states = dict()
        install_only_pkgs = []
        gpg_keys = []
        upgrade_pkgs = []

        # Remove extra instances.
        # Can not reverify because we don't have a package entry.
        if len(self.extra_instances) > 0:
            if (Bcfg2.Options.setup.remove in ['all', 'packages'] and
                not Bcfg2.Options.setup.dry_run):
                self.Remove(self.extra_instances)
            else:
                self.logger.info("The following extra package instances will be removed by the '-r' option:")
                for pkg in self.extra_instances:
                    for inst in pkg:
                        self.logger.info("    %s %s" % (pkg.get('name'), self.str_evra(inst)))

        # Figure out which instances of the packages actually need something
        # doing to them and place in the appropriate work 'queue'.
        for pkg in packages:
            for inst in [instn for instn in pkg if instn.tag \
                         in ['Instance', 'Package']]:
                if self.FixInstance(inst, self.instance_status[inst]):
                    if pkg.get('name') == 'gpg-pubkey':
                        gpg_keys.append(inst)
                    elif pkg.get('name') in self.installOnlyPkgs:
                        install_only_pkgs.append(inst)
                    else:
                        upgrade_pkgs.append(inst)

        # Fix installOnlyPackages
        if len(install_only_pkgs) > 0:
            self.logger.info("Attempting to install 'install only packages'")
            install_args = \
                " ".join(os.path.join(self.instance_status[inst].get('pkg').get('uri'),
                                      inst.get('simplefile'))
                         for inst in install_only_pkgs)
            if self.cmd.run("rpm --install --quiet --oldpackage --replacepkgs "
                            "%s" % install_args):
                # The rpm command succeeded.  All packages installed.
                self.logger.info("Single Pass for InstallOnlyPkgs Succeded")
                self.RefreshPackages()
            else:
                # The rpm command failed.  No packages installed.
                # Try installing instances individually.
                self.logger.error("Single Pass for InstallOnlyPackages Failed")
                installed_instances = []
                for inst in install_only_pkgs:
                    install_args = \
                        os.path.join(self.instance_status[inst].get('pkg').get('uri'),
                                     inst.get('simplefile'))
                    if self.cmd.run("rpm --install --quiet --oldpackage "
                                    "--replacepkgs %s" % install_args):
                        installed_instances.append(inst)
                    else:
                        self.logger.debug("InstallOnlyPackage %s %s would not install." % \
                                              (self.instance_status[inst].get('pkg').get('name'), \
                                               self.str_evra(inst)))

                install_pkg_set = set([self.instance_status[inst].get('pkg') \
                                                      for inst in install_only_pkgs])
                self.RefreshPackages()

        # Install GPG keys.
        if len(gpg_keys) > 0:
            for inst in gpg_keys:
                self.logger.info("Installing GPG keys.")
                key_arg = os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                     inst.get('simplefile'))
                if not self.cmd.run("rpm --import %s" % key_arg):
                    self.logger.debug("Unable to install %s-%s" %
                                      (self.instance_status[inst].get('pkg').get('name'),
                                       self.str_evra(inst)))
                else:
                    self.logger.debug("Installed %s-%s-%s" %
                                      (self.instance_status[inst].get('pkg').get('name'),
                                       inst.get('version'),
                                       inst.get('release')))
            self.RefreshPackages()
            self.gpg_keyids = self.getinstalledgpg()
            pkg = self.instance_status[gpg_keys[0]].get('pkg')
            states[pkg] = self.VerifyPackage(pkg, [])

        # Fix upgradeable packages.
        if len(upgrade_pkgs) > 0:
            self.logger.info("Attempting to upgrade packages")
            upgrade_args = " ".join([os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                  inst.get('simplefile')) \
                                           for inst in upgrade_pkgs])
            if self.cmd.run("rpm --upgrade --quiet --oldpackage --replacepkgs "
                            "%s" % upgrade_args):
                # The rpm command succeeded.  All packages upgraded.
                self.logger.info("Single Pass for Upgraded Packages Succeded")
                upgrade_pkg_set = set([self.instance_status[inst].get('pkg')
                                       for inst in upgrade_pkgs])
                self.RefreshPackages()
            else:
                # The rpm command failed.  No packages upgraded.
                # Try upgrading instances individually.
                self.logger.error("Single Pass for Upgrading Packages Failed")
                upgraded_instances = []
                for inst in upgrade_pkgs:
                    upgrade_args = os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                     inst.get('simplefile'))
                    #self.logger.debug("rpm --upgrade --quiet --oldpackage --replacepkgs %s" % \
                    #                                                      upgrade_args)
                    if self.cmd.run("rpm --upgrade --quiet --oldpackage "
                                    "--replacepkgs %s" % upgrade_args):
                        upgraded_instances.append(inst)
                    else:
                        self.logger.debug("Package %s %s would not upgrade." %
                                          (self.instance_status[inst].get('pkg').get('name'),
                                           self.str_evra(inst)))

                upgrade_pkg_set = set([self.instance_status[inst].get('pkg') \
                                                      for inst in upgrade_pkgs])
                self.RefreshPackages()

        if not Bcfg2.Options.setup.kevlar:
            for pkg_entry in packages:
                self.logger.debug("Reverifying Failed Package %s" % (pkg_entry.get('name')))
                states[pkg_entry] = self.VerifyPackage(pkg_entry, \
                                                       self.modlists.get(pkg_entry, []))

        self.modified.extend(ent for ent in packages if states[ent])
        return states

    def canInstall(self, entry):
        """Test if entry has enough information to be installed."""
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Cannot install entry %s:%s with bind failure" % \
                              (entry.tag, entry.get('name')))
            return False


        instances = entry.findall('Instance')

        # If the entry wasn't verifiable, then we really don't want to try and fix something
        # that we don't know is broken.
        if not self.canVerify(entry):
            self.logger.debug("WARNING: Package %s was not verifiable, not passing to Install()" \
                                           % entry.get('name'))
            return False

        if not instances:
            # Old non Instance format, unmodified.
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__gpg_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    return False
            else:
                if [attr for attr in self.__ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    return False
        else:
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_gpg_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__new_gpg_ireq__[inst.tag] \
                                 if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot install"\
                                          % (inst.tag, entry.get('name')))
                        return False
            else:
                # New format with Instances.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    self.logger.error("             Required attributes that may not be present are %s" \
                                      % (self.__new_ireq__[entry.tag]))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if inst.tag == 'Instance':
                        if [attr for attr in self.__new_ireq__[inst.tag] \
                                     if attr not in inst.attrib]:
                            self.logger.error("Incomplete information for %s of package %s; cannot install" \
                                              % (inst.tag, entry.get('name')))
                            self.logger.error("         Required attributes that may not be present are %s" \
                                              % (self.__new_ireq__[inst.tag]))
                            return False
        return True

    def canVerify(self, entry):
        """
            Test if entry has enough information to be verified.

            Three types of entries are checked.
               Old style Package
               New style Package with Instances
               pgp-pubkey packages

           Also the old style entries get modified after the first
           VerifyPackage() run, so there needs to be a second test.

        """
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Entry %s:%s reports bind failure: %s" % \
                              (entry.tag, entry.get('name'), entry.get('failure')))
            return False

        # We don't want to do any checks so we don't care what the entry has in it.
        if (not Bcfg2.Options.setup.rpm_pkg_checks or
            entry.get('pkg_checks', 'true').lower() == 'false'):
            return True

        instances = entry.findall('Instance')

        if not instances:
            # Old non Instance format, unmodified.
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__gpg_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
            elif entry.tag == 'Path' and entry.get('type') == 'ignore':
                # ignored Paths are only relevant during failed package
                # verification
                pass
            else:
                if [attr for attr in self.__req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
        else:
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_gpg_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__new_gpg_req__[inst.tag] \
                                 if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                          % (inst.tag, inst.get('name')))
                        return False
            else:
                # New format with Instances, or old style modified.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if inst.tag == 'Instance':
                        if [attr for attr in self.__new_req__[inst.tag] \
                                     if attr not in inst.attrib]:
                            self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                              % (inst.tag, inst.get('name')))
                            return False
        return True

    def FindExtra(self):
        """Find extra packages."""
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        extras = []

        for (name, instances) in list(self.installed.items()):
            if name not in packages:
                extra_entry = Bcfg2.Client.XML.Element('Package', name=name, type=self.pkgtype)
                for installed_inst in instances:
                    if Bcfg2.Options.setup.extra:
                        self.logger.info("Extra Package %s %s." % \
                                         (name, self.str_evra(installed_inst)))
                    tmp_entry = Bcfg2.Client.XML.SubElement(extra_entry, 'Instance', \
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    if installed_inst.get('epoch', None) != None:
                        tmp_entry.set('epoch', str(installed_inst.get('epoch')))
                    if installed_inst.get('arch', None) != None:
                        tmp_entry.set('arch', installed_inst.get('arch'))
                extras.append(extra_entry)
        return extras

    def FindExtraInstances(self, pkg_entry, installed_entry):
        """
            Check for installed instances that are not in the config.
            Return a Package Entry with Instances to remove, or None if there
            are no Instances to remove.

        """
        name = pkg_entry.get('name')
        extra_entry = Bcfg2.Client.XML.Element('Package', name=name, type=self.pkgtype)
        instances = [inst for inst in pkg_entry if inst.tag == 'Instance' or inst.tag == 'Package']
        if name in self.installOnlyPkgs:
            for installed_inst in installed_entry:
                not_found = True
                for inst in instances:
                    if self.pkg_vr_equal(inst, installed_inst) or \
                       self.inst_evra_equal(inst, installed_inst):
                        not_found = False
                        break
                if not_found == True:
                    # Extra package.
                    self.logger.info("Extra InstallOnlyPackage %s %s." % \
                                     (name, self.str_evra(installed_inst)))
                    tmp_entry = Bcfg2.Client.XML.SubElement(extra_entry, 'Instance', \
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    if installed_inst.get('epoch', None) != None:
                        tmp_entry.set('epoch', str(installed_inst.get('epoch')))
                    if installed_inst.get('arch', None) != None:
                        tmp_entry.set('arch', installed_inst.get('arch'))
        else:
            # Normal package, only check arch.
            for installed_inst in installed_entry:
                not_found = True
                for inst in instances:
                    if installed_inst.get('arch', None) == inst.get('arch', None) or\
                       inst.tag == 'Package':
                        not_found = False
                        break
                if not_found:
                    self.logger.info("Extra Normal Package Instance %s %s" % \
                                     (name, self.str_evra(installed_inst)))
                    tmp_entry = Bcfg2.Client.XML.SubElement(extra_entry, 'Instance', \
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    if installed_inst.get('epoch', None) != None:
                        tmp_entry.set('epoch', str(installed_inst.get('epoch')))
                    if installed_inst.get('arch', None) != None:
                        tmp_entry.set('arch', installed_inst.get('arch'))

        if len(extra_entry) == 0:
            extra_entry = None

        return extra_entry

    def str_evra(self, instance):
        """Convert evra dict entries to a string."""
        if instance.get('epoch', '*') in ['*', None]:
            return '%s-%s.%s' % (instance.get('version', '*'),
                                 instance.get('release', '*'),
                                 instance.get('arch', '*'))
        else:
            return '%s:%s-%s.%s' % (instance.get('epoch', '*'),
                                    instance.get('version', '*'),
                                    instance.get('release', '*'),
                                    instance.get('arch', '*'))

    def pkg_vr_equal(self, config_entry, installed_entry):
        '''
            Compare old style entry to installed entry.  Which means ignore
            the epoch and arch.
        '''
        if (config_entry.tag == 'Package' and \
            config_entry.get('version') == installed_entry.get('version') and \
            config_entry.get('release') == installed_entry.get('release')):
            return True
        else:
            return False

    def inst_evra_equal(self, config_entry, installed_entry):
        """Compare new style instance to installed entry."""

        if config_entry.get('epoch', None) != None:
            epoch = int(config_entry.get('epoch'))
        else:
            epoch = None

        if (config_entry.tag == 'Instance' and \
           (epoch == installed_entry.get('epoch', 0) or \
               (epoch == 0 and installed_entry.get('epoch', 0) == None) or \
               (epoch == None and installed_entry.get('epoch', 0) == 0)) and \
           config_entry.get('version') == installed_entry.get('version') and \
           config_entry.get('release') == installed_entry.get('release') and \
           config_entry.get('arch', None) == installed_entry.get('arch', None)):
            return True
        else:
            return False

    def getinstalledgpg(self):
        """
           Create a list of installed GPG key IDs.

           The pgp-pubkey package version is the least significant 4 bytes
           (big-endian) of the key ID which is good enough for our purposes.

        """
        init_ts = rpmtransactionset()
        init_ts.setVSFlags(rpm._RPMVSF_NODIGESTS|rpm._RPMVSF_NOSIGNATURES)
        gpg_hdrs = getheadersbykeyword(init_ts, **{'name':'gpg-pubkey'})
        keyids = [ header[rpm.RPMTAG_VERSION] for header in gpg_hdrs]
        keyids.append('None')
        init_ts.closeDB()
        del init_ts
        return keyids

    def VerifyPath(self, entry, _):
        """
           We don't do anything here since all
           Paths are processed in __init__
        """
        return True
