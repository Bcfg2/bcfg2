import lxml.etree
import glob
import re
import Bcfg2.Server.Admin
from Bcfg2.metargs import Option
import Bcfg2.Options

class Bundle(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Create or delete bundle entries"
    # TODO: add/del functions
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin bundle list-xml"
                                    "\nbcfg2-admin bundle list-genshi"
                                    "\nbcfg2-admin bundle show\n")
    __usage__ = ("bcfg2-admin bundle [options] [add|del] [group]")

    def __init__(self):
        Bcfg2.Server.Admin.MetadataCore.__init__(self)
        Bcfg2.Options.set_help(self.__shorthelp__)
        Bcfg2.Options.add_options(
            Bcfg2.Options.SERVER_REPOSITORY,
            Option('command', help='Bundle command to execute',
                   choices=['list-xml', 'ls-xml', 'list-genshi', 'ls-gen', 'show']),
        )

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        rg = re.compile(r'([^.]+\.(?:[a-z][a-z\-]+))(?![\w\.])',
                        re.IGNORECASE | re.DOTALL)

        # Get all bundles out of the Bundle/ directory
        repo = args.repository_path
        xml_list = glob.glob("%s/Bundler/*.xml" % repo)
        genshi_list = glob.glob("%s/Bundler/*.genshi" % repo)

#        if args.command == 'add':
#            try:
#                self.metadata.add_bundle(args[1])
#            except MetadataConsistencyError:
#                print("Error in adding bundle.")
#                raise SystemExit(1)
#        elif args.command in ['delete', 'remove', 'del', 'rm']:
#            try:
#                self.metadata.remove_bundle(args[1])
#            except MetadataConsistencyError:
#                print("Error in deleting bundle.")
#                raise SystemExit(1)
        # Lists all available xml bundles
        if args.command in ['list-xml', 'ls-xml']:
            bundle_name = []
            for bundle_path in xml_list:
                bundle_name.append(rg.search(bundle_path).group(1))
            for bundle in bundle_name:
                print(bundle.split('.')[0])
        # Lists all available genshi bundles
        elif args.command in ['list-genshi', 'ls-gen']:
            bundle_name = []
            for bundle_path in genshi_list:
                bundle_name.append(rg.search(bundle_path).group(1))
            for bundle in bundle_name:
                print(bundle.split('.')[0])
        # Shows a list of all available bundles and prints bundle
        # details after the user choose one bundle.
        # FIXME: Add support for detailed output of genshi bundles
        # FIXME: This functionality is almost identical with
        #        bcfg2-info bundles
        elif args.command in ['show']:
            bundle_name = []
            bundle_list = xml_list + genshi_list
            for bundle_path in bundle_list:
                print "matching %s" % bundle_path
                bundle_name.append(rg.search(bundle_path).group(1))
            text = "Available bundles (Number of bundles: %s)" % \
                    (len(bundle_list))
            print(text)
            print("%s" % (len(text) * "-"))
            for i in range(len(bundle_list)):
                print("[%i]\t%s" % (i, bundle_name[i]))
            try:
                lineno = raw_input("Enter the line number of a bundle for details: ")
            except NameError:
                lineno = input("Enter the line number of a bundle for details: ")
            if int(lineno) >= int(len(bundle_list)):
                print("No line with this number.")
            else:
                if '%s/Bundler/%s' % \
                            (repo, bundle_name[int(lineno)]) in genshi_list:
                    print("Detailed output for *.genshi bundles is not supported.")
                else:
                    print('Details for the "%s" bundle:' % \
                            (bundle_name[int(lineno)].split('.')[0]))
                    tree = lxml.etree.parse(bundle_list[int(lineno)])
                    #Prints bundle content
                    #print(lxml.etree.tostring(tree))
                    names = ['Action', 'Package', 'Path', 'Service']
                    for name in names:
                        for node in tree.findall("//" + name):
                            print("%s:\t%s" % (name, node.attrib["name"]))
        else:
            print("No command specified")
            raise SystemExit(1)
