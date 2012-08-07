"""
1_2_x.py

This file should contain updates relevant to the 1.2.x branches ONLY.
The updates() method must be defined and it should return an Updater object
"""
from Bcfg2.Server.SchemaUpdater import Updater
from Bcfg2.Server.SchemaUpdater.Routines import updatercallable

def updates():
    fixes = Updater("1.2")
    fixes.override_base_version(18) # Do not do this in new code
    fixes.add('alter table reports_reason add is_sensitive bool NOT NULL default False;')
    return fixes

