"""
1_0_x.py

This file should contain updates relevant to the 1.0.x branches ONLY.
The updates() method must be defined and it should return an Updater object
"""
from Bcfg2.Server.Reports.Updater import UnsupportedUpdate

def updates():
    return UnsupportedUpdate("1.0", 10)

