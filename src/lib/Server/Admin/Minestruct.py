import Bcfg2.Server.Admin

class Minestruct(Bcfg2.Server.Admin.Mode):
    '''Pull extra entries out of statistics'''
    __shorthelp__ = 'bcfg2-admin minestruct <client>'
    __longhelp__ = __shorthelp__ + '\n\tExtract extra entry lists from statistics'
    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) != 1:
            self.errExit("minestruct must be called with a client name")
        extra = self.MineStruct(args[0])
        self.log.info("Found %d extra entries" % (len(extra)))
        self.log.info(["%s: %s" % (entry.tag, entry.get('name')) for entry in extra])

    def MineStruct(self, client):
        '''Pull client entries into structure'''
        stats = self.load_stats(client)
        if len(stats.getchildren()) == 2:
            # FIXME this is busted
            # client is dirty
            current = [ent for ent in stats.getchildren() if ent.get('state') == 'dirty'][0]
        else:
            current = stats.getchildren()[0]
        return current.find('Extra').getchildren()

