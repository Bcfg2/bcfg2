import sys
import os


def env_setup():
    os.environ['bcfg_db_engine'] = 'foo'
    os.environ['bcfg_db_name'] = 'bar'
    os.environ['bcfg_db_user'] = 'baz'
    os.environ['bcfg_db_password'] = 'pass'
    os.environ['bcfg_db_host'] = 'biff'
    os.environ['bcfg_db_port'] = '3306'
    os.environ['bcfg_time_zone'] = 'CHI'

def teardown():
    pass

def test_environ_settings():

    os.environ['bcfg_db_engine'] = 'foo'
    os.environ['bcfg_db_name'] = 'bar'
    os.environ['bcfg_db_user'] = 'baz'
    os.environ['bcfg_db_password'] = 'pass'
    os.environ['bcfg_db_host'] = 'biff'
    os.environ['bcfg_db_port'] = '3306'
    os.environ['bcfg_time_zone'] = 'CHI'
    import Hostbase.settings
    s = Hostbase.settings
    s.CFG_TYPE = 'environ'
    assert s.DATABASE_ENGINE == 'mysql'
    assert s.DATABASE_PASSWORD == 'pass'
    assert s.DATABASE_NAME == 'bar'
    assert s.DATABASE_USER == 'baz'
    assert s.DATABASE_HOST == 'biff'
    assert s.DATABASE_PORT == '3306'
    assert s.TIME_ZONE == 'CHI'
