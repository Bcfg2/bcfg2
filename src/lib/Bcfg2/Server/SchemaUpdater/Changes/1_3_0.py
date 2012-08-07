"""
1_3_0.py

This file should contain updates relevant to the 1.3.x branches ONLY.
The updates() method must be defined and it should return an Updater object
"""
from Bcfg2.Server.SchemaUpdater import Updater, UpdaterError
from Bcfg2.Server.SchemaUpdater.Routines import AddColumns, \
        RemoveColumns, RebuildTable, DropTable

from Bcfg2.Server.Reports.reports.models import Reason, Interaction


def updates():
    fixes = Updater("1.3")
    fixes.add(RemoveColumns(Interaction, 'client_version'))
    fixes.add(AddColumns(Reason))
    fixes.add(RebuildTable(Reason, [
               'owner', 'current_owner',
               'group', 'current_group',
               'perms', 'current_perms',
               'status', 'current_status',
               'to', 'current_to']))
    fixes.add(DropTable('reports_ping'))

    return fixes

