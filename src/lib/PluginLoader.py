from pkg_resources import iter_entry_points

class MultipleEntriesError(Exception):
    def __init__(self, group, name):
        projects = ", ".join(ep.dist.project_name
                             for ep
                             in iter_entry_points(group, name))
        Exception.__init__(self,
            "More than one entry named %s available in group %s. "
            "Entries were found in the following packages: %s" % (
                name, group, projects))

class NoEntriesError(Exception):
    def __init__(self, group, name):
        Exception.__init__(self, "No entries found named %s in group %s" % (name, group))

def load_exactly_one(group, name):
    """
    Loads all entry points named ``name`` in ``group``. Returns the loaded
    entry_point (ready to be called)

    If there is more than one such entry point, raises MultipleEntriesError
    If there are no entries, raises NoEntriesError
    """
    entries = list(iter_entry_points(group, name))
    if len(entries) > 1:
        raise MultipleEntriesError(group, name)

    if len(entries) == 0:
        raise NoEntriesError(group, name)

    return entries[0].load()

