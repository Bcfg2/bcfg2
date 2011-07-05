import lxml.etree
import os

import Bcfg2.Server.Admin


class Compare(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Determine differences between files or "
                     "directories of client specification instances")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin compare <file1> <file2>"
                                    "\nbcfg2-admin compare -r <dir1> <dir2>")
    __usage__ = ("bcfg2-admin compare <old> <new>\n\n"
                 "     -r\trecursive")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)
        self.important = {'Package': ['name', 'version'],
                          'Service': ['name', 'status'],
                          'Directory': ['name', 'owner', 'group', 'perms'],
                          'SymLink': ['name', 'to'],
                          'ConfigFile': ['name', 'owner', 'group', 'perms'],
                          'Permissions': ['name', 'perms'],
                          'PostInstall': ['name']}

    def compareStructures(self, new, old):
        for child in new.getchildren():
            equiv = old.xpath('%s[@name="%s"]' %
                             (child.tag, child.get('name')))
            if child.tag in self.important:
                print("tag type %s not handled" % (child.tag))
                continue
            if len(equiv) == 0:
                print("didn't find matching %s %s" %
                     (child.tag, child.get('name')))
                continue
            elif len(equiv) >= 1:
                if child.tag == 'ConfigFile':
                    if child.text != equiv[0].text:
                        print(" %s %s contents differ" \
                              % (child.tag, child.get('name')))
                        continue
                noattrmatch = [field for field in self.important[child.tag] if \
                               child.get(field) != equiv[0].get(field)]
                if not noattrmatch:
                    new.remove(child)
                    old.remove(equiv[0])
                else:
                    print(" %s %s attributes %s do not match" % \
                          (child.tag, child.get('name'), noattrmatch))
        if len(old.getchildren()) == 0 and len(new.getchildren()) == 0:
            return True
        if new.tag == 'Independent':
            name = 'Base'
        else:
            name = new.get('name')
        both = []
        oldl = ["%s %s" % (entry.tag, entry.get('name')) for entry in old]
        newl = ["%s %s" % (entry.tag, entry.get('name')) for entry in new]
        for entry in newl:
            if entry in oldl:
                both.append(entry)
                newl.remove(entry)
                oldl.remove(entry)
        for entry in both:
            print(" %s differs (in bundle %s)" % (entry, name))
        for entry in oldl:
            print(" %s only in old configuration (in bundle %s)" % (entry,
                                                                    name))
        for entry in newl:
            print(" %s only in new configuration (in bundle %s)" % (entry,
                                                                    name))
        return False

    def compareSpecifications(self, path1, path2):
        try:
            new = lxml.etree.parse(path1).getroot()
        except IOError:
            print("Failed to read %s" % (path1))
            raise SystemExit(1)

        try:
            old = lxml.etree.parse(path2).getroot()
        except IOError:
            print("Failed to read %s" % (path2))
            raise SystemExit(1)

        for src in [new, old]:
            for bundle in src.findall('./Bundle'):
                if bundle.get('name')[-4:] == '.xml':
                    bundle.set('name', bundle.get('name')[:-4])

        rcs = []
        for bundle in new.findall('./Bundle'):
            equiv = old.xpath('Bundle[@name="%s"]' % (bundle.get('name')))
            if len(equiv) == 0:
                print("couldnt find matching bundle for %s" % bundle.get('name'))
                continue
            if len(equiv) == 1:
                if self.compareStructures(bundle, equiv[0]):
                    new.remove(bundle)
                    old.remove(equiv[0])
                    rcs.append(True)
                else:
                    rcs.append(False)
            else:
                print("Unmatched bundle %s" % (bundle.get('name')))
                rcs.append(False)
        i1 = new.find('./Independent')
        i2 = old.find('./Independent')
        if self.compareStructures(i1, i2):
            new.remove(i1)
            old.remove(i2)
        else:
            rcs.append(False)
        return False not in rcs

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Please see bcfg2-admin compare help for usage.")
        if '-r' in args:
            args = list(args)
            args.remove('-r')
            (oldd, newd) = args
            (old, new) = [os.listdir(spot) for spot in args]
            for item in old:
                print("Entry:", item)
                state = self.__call__([oldd + '/' + item, newd + '/' + item])
                new.remove(item)
                if state:
                    print("Entry:", item, "good")
                else:
                    print("Entry:", item, "bad")
            if new:
                print("new has extra entries", new)
            return
        try:
            (old, new) = args
            return self.compareSpecifications(new, old)
        except IndexError:
            print(self.__call__.__doc__)
            raise SystemExit(1)
