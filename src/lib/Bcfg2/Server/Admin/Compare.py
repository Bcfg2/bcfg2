import lxml.etree
import os
import Bcfg2.Server.Admin


class Compare(Bcfg2.Server.Admin.Mode):
    """ Determine differences between files or directories of client
    specification instances """
    __usage__ = ("<old> <new>\n\n"
                 "     -r\trecursive")

    def __init__(self, setup):
        Bcfg2.Server.Admin.Mode.__init__(self, setup)
        self.important = {'Path': ['name', 'type', 'owner', 'group', 'mode',
                                   'important', 'paranoid', 'sensitive',
                                   'dev_type', 'major', 'minor', 'prune',
                                   'encoding', 'empty', 'to', 'recursive',
                                   'vcstype', 'sourceurl', 'revision',
                                   'secontext'],
                          'Package': ['name', 'type', 'version', 'simplefile',
                                      'verify'],
                          'Service': ['name', 'type', 'status', 'mode',
                                      'target', 'sequence', 'parameters'],
                          'Action': ['name', 'timing', 'when', 'status',
                                     'command'],
                          'PostInstall': ['name']
                          }

    def compareStructures(self, new, old):
        if new.tag == 'Independent':
            bundle = 'Base'
        else:
            bundle = new.get('name')

        identical = True

        for child in new.getchildren():
            if child.tag not in self.important:
                print("  %s in (new) bundle %s:\n   tag type not handled!" %
                      (child.tag, bundle))
                continue
            equiv = old.xpath('%s[@name="%s"]' %
                              (child.tag, child.get('name')))
            if len(equiv) == 0:
                print("  %s %s in bundle %s:\n   only in new configuration" %
                      (child.tag, child.get('name'), bundle))
                identical = False
                continue
            diff = []
            if child.tag == 'Path' and child.get('type') == 'file' and \
               child.text != equiv[0].text:
                diff.append('contents')
            attrdiff = [field for field in self.important[child.tag] if \
                        child.get(field) != equiv[0].get(field)]
            if attrdiff:
                diff.append('attributes (%s)' % ', '.join(attrdiff))
            if diff:
                print("  %s %s in bundle %s:\n   %s differ" % (child.tag, \
                      child.get('name'), bundle, ' and '.join(diff)))
                identical = False

        for child in old.getchildren():
            if child.tag not in self.important:
                print("  %s in (old) bundle %s:\n   tag type not handled!" %
                      (child.tag, bundle))
            elif len(new.xpath('%s[@name="%s"]' %
                     (child.tag, child.get('name')))) == 0:
                print("  %s %s in bundle %s:\n   only in old configuration" %
                      (child.tag, child.get('name'), bundle))
                identical = False

        return identical

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

        identical = True

        for bundle in old.findall('./Bundle'):
            if len(new.xpath('Bundle[@name="%s"]' % (bundle.get('name')))) == 0:
                print(" Bundle %s only in old configuration" %
                      bundle.get('name'))
                identical = False
        for bundle in new.findall('./Bundle'):
            equiv = old.xpath('Bundle[@name="%s"]' % (bundle.get('name')))
            if len(equiv) == 0:
                print(" Bundle %s only in new configuration" %
                      bundle.get('name'))
                identical = False
            elif not self.compareStructures(bundle, equiv[0]):
                identical = False

        i1 = lxml.etree.Element('Independent')
        i2 = lxml.etree.Element('Independent')
        i1.extend(new.findall('./Independent/*'))
        i2.extend(old.findall('./Independent/*'))
        if not self.compareStructures(i1, i2):
            identical = False

        return identical

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
            old_extra = []
            for item in old:
                if item not in new:
                    old_extra.append(item)
                    continue
                print("File: %s" % item)
                state = self.__call__([oldd + '/' + item, newd + '/' + item])
                new.remove(item)
                if state:
                    print("File %s is good" % item)
                else:
                    print("File %s is bad" % item)
            if new:
                print("%s has extra files: %s" % (newd, ', '.join(new)))
            if old_extra:
                print("%s has extra files: %s" % (oldd, ', '.join(old_extra)))
            return
        try:
            (old, new) = args
            return self.compareSpecifications(new, old)
        except IndexError:
            self.errExit(self.__call__.__doc__)
