#!/usr/bin/env python
"""
    Module that uses rpm-python to implement the following rpm
    functionality for the bcfg2 RPM and YUM client drivers:

        rpm -qa
        rpm --verify
        rpm --erase

    The code closely follows the rpm C code.

    The code was written to be used in the bcfg2 RPM/YUM drivers.

    Some command line options have been provided to assist with
    testing and development, but the output isn't pretty and looks
    nothing like rpm output.

    Run 'rpmtools' -h for the options.

"""

import grp
import optparse
import os
import pwd
import rpm
import stat
import sys
if sys.version_info >= (2, 5):
    import hashlib
    py24compat = False
else:
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
