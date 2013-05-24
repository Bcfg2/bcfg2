"""
The base for the original DjangoORM (DBStats)
"""

import os
import traceback
from lxml import etree
from datetime import datetime
from time import strptime

os.environ['DJANGO_SETTINGS_MODULE'] = 'Bcfg2.settings'
from Bcfg2 import settings

from Bcfg2.Compat import md5
from Bcfg2.Reporting.Storage.base import StorageBase, StorageError
from Bcfg2.Server.Plugin.exceptions import PluginExecutionError
from django.core import management
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import FieldDoesNotExist
from django.core.cache import cache
from django.db import transaction

#Used by GetCurrentEntry
import difflib
from Bcfg2.Compat import b64decode
from Bcfg2.Reporting.models import *


class DjangoORM(StorageBase):
    def __init__(self, setup):
        super(DjangoORM, self).__init__(setup)
        self.size_limit = setup.get('reporting_file_limit')

    def _import_default(self, entry, state, entrytype=None, defaults=None,
                        mapping=None, boolean=None, xforms=None):
        """ Default entry importer.  Maps the entry (in state
        ``state``) to an appropriate *Entry object; by default, this
        is determined by the entry tag, e.g., from an Action entry an
        ActionEntry object is created.  This can be overridden with
        ``entrytype``, which should be the class to instantiate for
        this entry.

        ``defaults`` is an optional mapping of <attribute
        name>:<value> that will be used to set the default values for
        various attributes.

        ``mapping`` is a mapping of <field name>:<attribute name> that
        can be used to map fields that are named differently on the
        XML entry and in the database model.

        ``boolean`` is a list of attribute names that should be
        treated as booleans.

        ``xforms`` is a dict of <attribute name>:<function>, where the
        given function will be applied to the value of the named
        attribute before trying to store it in the database.
        """
        if entrytype is None:
            entrytype = globals()["%sEntry" % entry.tag]
        if defaults is None:
            defaults = dict()
        if mapping is None:
            mapping = dict()
        if boolean is None:
            boolean = []
        if xforms is None:
            xforms = dict()
        mapping['exists'] = 'current_exists'
        defaults['current_exists'] = 'true'
        boolean.append("current_exists")

        def boolean_xform(val):
            try:
                return val.lower() == "true"
            except AttributeError:
                return False

        for attr in boolean + ["current_exists"]:
            xforms[attr] = boolean_xform
        act_dict = dict(state=state)
        for fieldname in entrytype._meta.get_all_field_names():
            if fieldname in ['id', 'hash_key', 'state']:
                continue
            try:
                field = entrytype._meta.get_field(fieldname)
            except FieldDoesNotExist:
                continue
            attrname = mapping.get(fieldname, fieldname)
            val = entry.get(fieldname, defaults.get(attrname))
            act_dict[fieldname] = xforms.get(attrname, lambda v: v)(val)
        self.logger.debug("Adding %s:%s" % (entry.tag, entry.get("name")))
        return entrytype.entry_get_or_create(act_dict)

    def _import_Action(self, entry, state):
        return self._import_default(entry, state,
                                    defaults=dict(status='check', rc=-1),
                                    mapping=dict(output="rc"))

    def _import_Package(self, entry, state):
        name = entry.get('name')
        exists = entry.get('current_exists', default="true").lower() == "true"
        act_dict = dict(name=name, state=state, exists=exists,
                        target_version=entry.get('version', default=''),
                        current_version=entry.get('current_version',
                                                  default=''))

        # extra entries are a bit different.  They can have Instance
        # objects
        if not act_dict['target_version']:
            for instance in entry.findall("Instance"):
                # FIXME - this probably only works for rpms
                release = instance.get('release', '')
                arch = instance.get('arch', '')
                act_dict['current_version'] = instance.get('version')
                if release:
                    act_dict['current_version'] += "-" + release
                if arch:
                    act_dict['current_version'] += "." + arch
                self.logger.debug("Adding package %s %s" %
                                  (name, act_dict['current_version']))
                return PackageEntry.entry_get_or_create(act_dict)
        else:
            self.logger.debug("Adding package %s %s" %
                              (name, act_dict['target_version']))

            # not implemented yet
            act_dict['verification_details'] = \
                entry.get('verification_details', '')
            return PackageEntry.entry_get_or_create(act_dict)

    def _import_Path(self, entry, state):
        name = entry.get('name')
        exists = entry.get('current_exists', default="true").lower() == "true"
        path_type = entry.get("type").lower()
        act_dict = dict(name=name, state=state, exists=exists,
                        path_type=path_type)

        target_dict = dict(
            owner=entry.get('owner', default="root"),
            group=entry.get('group', default="root"),
            mode=entry.get('mode', default=entry.get('perms',
                                                     default=""))
        )
        fperm, created = FilePerms.objects.get_or_create(**target_dict)
        act_dict['target_perms'] = fperm

        current_dict = dict(
            owner=entry.get('current_owner', default=""),
            group=entry.get('current_group', default=""),
            mode=entry.get('current_mode',
                default=entry.get('current_perms', default=""))
        )
        fperm, created = FilePerms.objects.get_or_create(**current_dict)
        act_dict['current_perms'] = fperm

        if path_type in ('symlink', 'hardlink'):
            act_dict['target_path'] = entry.get('to', default="")
            act_dict['current_path'] = entry.get('current_to', default="")
            self.logger.debug("Adding link %s" % name)
            return LinkEntry.entry_get_or_create(act_dict)
        elif path_type == 'device':
            # TODO devices
            self.logger.warn("device path types are not supported yet")
            return

        # TODO - vcs output
        act_dict['detail_type'] = PathEntry.DETAIL_UNUSED
        if path_type == 'directory' and entry.get('prune', 'false') == 'true':
            unpruned_elist = [e.get('path') for e in entry.findall('Prune')]
            if unpruned_elist:
                act_dict['detail_type'] = PathEntry.DETAIL_PRUNED
                act_dict['details'] = "\n".join(unpruned_elist)
        elif entry.get('sensitive', 'false').lower() == 'true':
            act_dict['detail_type'] = PathEntry.DETAIL_SENSITIVE
        else:
            cdata = None
            if entry.get('current_bfile', None):
                act_dict['detail_type'] = PathEntry.DETAIL_BINARY
                cdata = entry.get('current_bfile')
            elif entry.get('current_bdiff', None):
                act_dict['detail_type'] = PathEntry.DETAIL_DIFF
                cdata = b64decode(entry.get('current_bdiff'))
            elif entry.get('current_diff', None):
                act_dict['detail_type'] = PathEntry.DETAIL_DIFF
                cdata = entry.get('current_bdiff')
            if cdata:
                if len(cdata) > self.size_limit:
                    act_dict['detail_type'] = PathEntry.DETAIL_SIZE_LIMIT
                    act_dict['details'] = md5(cdata).hexdigest()
                else:
                    act_dict['details'] = cdata
        self.logger.debug("Adding path %s" % name)
        return PathEntry.entry_get_or_create(act_dict)
        # TODO - secontext
        # TODO - acls

    def _import_Service(self, entry, state):
        return self._import_default(entry, state,
                                    defaults=dict(status='',
                                                  current_status='',
                                                  target_status=''),
                                    mapping=dict(status='target_status'))

    def _import_SEBoolean(self, entry, state):
        return self._import_default(
            entry, state,
            xforms=dict(value=lambda v: v.lower() == "on"))

    def _import_SEFcontext(self, entry, state):
        return self._import_default(entry, state,
                                    defaults=dict(filetype='all'))

    def _import_SEInterface(self, entry, state):
        return self._import_default(entry, state)

    def _import_SEPort(self, entry, state):
        return self._import_default(entry, state)

    def _import_SENode(self, entry, state):
        return self._import_default(entry, state)

    def _import_SELogin(self, entry, state):
        return self._import_default(entry, state)

    def _import_SEUser(self, entry, state):
        return self._import_default(entry, state)

    def _import_SEPermissive(self, entry, state):
        return self._import_default(entry, state)

    def _import_SEModule(self, entry, state):
        return self._import_default(entry, state,
                                    defaults=dict(disabled='false'),
                                    boolean=['disabled', 'current_disabled'])

    def _import_POSIXUser(self, entry, state):
        defaults = dict(group=entry.get("name"),
                        gecos=entry.get("name"),
                        shell='/bin/bash',
                        uid=entry.get("current_uid"))
        if entry.get('name') == 'root':
            defaults['home'] = '/root'
        else:
            defaults['home'] = '/home/%s' % entry.get('name')

        # TODO: supplementary group membership
        return self._import_default(entry, state, defaults=defaults)

    def _import_POSIXGroup(self, entry, state):
        return self._import_default(
            entry, state,
            defaults=dict(gid=entry.get("current_gid")))

    def _import_unknown(self, entry, _):
        self.logger.error("Unknown type %s not handled by reporting yet" %
                          entry.tag)
        return None

    @transaction.commit_on_success
    def _import_interaction(self, interaction):
        """Real import function"""
        hostname = interaction['hostname']
        stats = etree.fromstring(interaction['stats'])
        metadata = interaction['metadata']
        server = metadata['server']

        client = cache.get(hostname)
        if not client:
            client, created = Client.objects.get_or_create(name=hostname)
            if created:
                self.logger.debug("Client %s added to the db" % hostname)
            cache.set(hostname, client)

        timestamp = datetime(*strptime(stats.get('time'))[0:6])
        if len(Interaction.objects.filter(client=client,
                                          timestamp=timestamp)) > 0:
            self.logger.warn("Interaction for %s at %s already exists" %
                    (hostname, timestamp))
            return

        if 'profile' in metadata:
            profile, created = \
                Group.objects.get_or_create(name=metadata['profile'])
        else:
            profile = None
        inter = Interaction(client=client,
                             timestamp=timestamp,
                             state=stats.get('state', default="unknown"),
                             repo_rev_code=stats.get('revision',
                                                          default="unknown"),
                             good_count=stats.get('good', default="0"),
                             total_count=stats.get('total', default="0"),
                             server=server,
                             profile=profile)
        inter.save()
        self.logger.debug("Interaction for %s at %s with INSERTED in to db" %
                (client.id, timestamp))

        # FIXME - this should be more efficient
        for group_name in metadata['groups']:
            group = cache.get("GROUP_" + group_name)
            if not group:
                group, created = Group.objects.get_or_create(name=group_name)
                if created:
                    self.logger.debug("Added group %s" % group)
                cache.set("GROUP_" + group_name, group)

            inter.groups.add(group)
        for bundle_name in metadata.get('bundles', []):
            bundle = cache.get("BUNDLE_" + bundle_name)
            if not bundle:
                bundle, created = \
                    Bundle.objects.get_or_create(name=bundle_name)
                if created:
                    self.logger.debug("Added bundle %s" % bundle)
                cache.set("BUNDLE_" + bundle_name, bundle)
            inter.bundles.add(bundle)
        inter.save()

        counter_fields = {TYPE_BAD: 0,
                          TYPE_MODIFIED: 0,
                          TYPE_EXTRA: 0}
        pattern = [('Bad/*', TYPE_BAD),
                   ('Extra/*', TYPE_EXTRA),
                   ('Modified/*', TYPE_MODIFIED)]
        updates = dict([(etype, []) for etype in Interaction.entry_types])
        for (xpath, state) in pattern:
            for entry in stats.findall(xpath):
                counter_fields[state] = counter_fields[state] + 1

                # handle server failures differently
                failure = entry.get('failure', '')
                if failure:
                    act_dict = dict(name=entry.get("name"),
                                    entry_type=entry.tag,
                                    message=failure)
                    newact = FailureEntry.entry_get_or_create(act_dict)
                    updates['failures'].append(newact)
                    continue

                updatetype = entry.tag.lower() + "s"
                update = getattr(self, "_import_%s" % entry.tag,
                                 self._import_unknown)(entry, state)
                if update is not None:
                    updates[updatetype].append(update)

        inter.bad_count = counter_fields[TYPE_BAD]
        inter.modified_count = counter_fields[TYPE_MODIFIED]
        inter.extra_count = counter_fields[TYPE_EXTRA]
        inter.save()
        for entry_type in updates.keys():
            # batch this for sqlite
            i = 0
            while(i < len(updates[entry_type])):
                getattr(inter, entry_type).add(*updates[entry_type][i:i + 100])
                i += 100

        # performance metrics
        for times in stats.findall('OpStamps'):
            for metric, value in list(times.items()):
                Performance(interaction=inter,
                            metric=metric,
                            value=value).save()

    def import_interaction(self, interaction):
        """Import the data into the backend"""

        try:
            self._import_interaction(interaction)
        except:
            self.logger.error("Failed to import interaction: %s" %
                    traceback.format_exc().splitlines()[-1])

    def validate(self):
        """Validate backend storage.  Should be called once when loaded"""

        settings.read_config(repo=self.setup['repo'])

        # verify our database schema
        try:
            if self.setup['debug']:
                vrb = 2
            elif self.setup['verbose']:
                vrb = 1
            else:
                vrb = 0
            management.call_command("syncdb", verbosity=vrb, interactive=False)
            management.call_command("migrate", verbosity=vrb, interactive=False)
        except:
            self.logger.error("Failed to update database schema: %s" % \
                traceback.format_exc().splitlines()[-1])
            raise StorageError

    def GetExtra(self, client):
        """Fetch extra entries for a client"""
        try:
            c_inst = Client.objects.get(name=client)
            if not c_inst.current_interaction:
                # the rare case where a client has no interations
                return None
            return [(ent.entry_type, ent.name) for ent in
                    c_inst.current_interaction.extra()]
        except ObjectDoesNotExist:
            return []
        except MultipleObjectsReturned:
            self.logger.error("%s Inconsistency: Multiple entries for %s." %
                (self.__class__.__name__, client))
            return []

    def GetCurrentEntry(self, client, e_type, e_name):
        """"GetCurrentEntry: Used by PullSource"""
        try:
            c_inst = Client.objects.get(name=client)
        except ObjectDoesNotExist:
            self.logger.error("Unknown client: %s" % client)
            raise PluginExecutionError
        except MultipleObjectsReturned:
            self.logger.error("%s Inconsistency: Multiple entries for %s." %
                (self.__class__.__name__, client))
            raise PluginExecutionError
        try:
            cls = BaseEntry.entry_from_name(e_type + "Entry")
            result = cls.objects.filter(name=e_name, state=TYPE_BAD,
                interaction=c_inst.current_interaction)
        except ValueError:
            self.logger.error("Unhandled type %s" % e_type)
            raise PluginExecutionError
        if not result:
            raise PluginExecutionError
        entry = result[0]
        ret = []
        for p_entry in ('owner', 'group', 'mode'):
            this_entry = getattr(entry.current_perms, p_entry)
            if this_entry == '':
                ret.append(getattr(entry.target_perms, p_entry))
            else:
                ret.append(this_entry)
        if entry.entry_type == 'Path':
            if entry.is_sensitive():
                raise PluginExecutionError
            elif entry.detail_type == PathEntry.DETAIL_PRUNED:
                ret.append('\n'.join(entry.details))
            elif entry.is_binary():
                ret.append(b64decode(entry.details))
            elif entry.is_diff():
                ret.append('\n'.join(difflib.restore(\
                    entry.details.split('\n'), 1)))
            elif entry.is_too_large():
                # If len is zero the object was too large to store
                raise PluginExecutionError
            else:
                ret.append(None)
        return ret

