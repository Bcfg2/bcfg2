#!/usr/bin/env python
""" Wrapper for the django manage.py with the Bcfg2 Opitons parsing. """

import sys
import django
import Bcfg2.Options
import Bcfg2.DBSettings

try:
    import Bcfg2.Server.models
except ImportError:
    pass


def main():
    parser = Bcfg2.Options.get_parser()
    parser.add_options([
        Bcfg2.Options.PositionalArgument('django_command', nargs='*')])
    parser.parse()

    if django.VERSION[0] == 1 and django.VERSION[1] >= 6:
        from django.core.management import execute_from_command_line
        execute_from_command_line(
            sys.argv[:1] + Bcfg2.Options.setup.django_command)
    else:
        from django.core.management import execute_manager
        execute_manager(Bcfg2.DBSettings.settings)


if __name__ == "__main__":
    main()
