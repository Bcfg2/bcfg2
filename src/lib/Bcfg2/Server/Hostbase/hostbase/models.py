from django.db import models

# Create your models here.
class Host(models.Model):
    NETGROUP_CHOICES = (
        ('none', 'none'),('cave', 'cave'),('ccst', 'ccst'),('mcs', 'mcs'),
        ('mmlab', 'mmlab'),('sp', 'sp'),('red', 'red'),('virtual', 'virtual'),
        ('win', 'win'),('xterm', 'xterm'),('lcrc', 'lcrc'),('anlext', 'anlext'),
        ('teragrid', 'teragrid')
        )
    STATUS_CHOICES = (
        ('active','active'),('dormant','dormant')
        )
    SUPPORT_CHOICES = (
        ('green','green'),('yellow','yellow'),('red','red')
        )
    CLASS_CHOICES = (
        ('scientific','scientific'),
        ('operations','operations'),('guest','guest'),
        ('confidential','confidential'),('public','public')
        )
    WHATAMI_CHOICES = (
        ('aix-3', 'aix-3'), ('aix-4', 'aix-4'),
        ('aix-5', 'aix-5'), ('baytech', 'baytech'),
        ('decserver', 'decserver'), ('dialup', 'dialup'),
        ('dos', 'dos'), ('freebsd', 'freebsd'),
        ('hpux', 'hpux'), ('irix-5', 'irix-5'),
        ('irix-6', 'irix-6'), ('linux', 'linux'),
        ('linux-2', 'linux-2'), ('linux-rh73', 'linux-rh73'),
        ('linux-rh8', 'linux-rh8'), ('linux-sles8', 'linux-sles8'),
        ('linux-sles8-64', 'linux-sles8-64'), ('linux-sles8-ia32', 'linux-sles8-ia32'),
        ('linux-sles8-ia64', 'linux-sles8-ia64'), ('mac', 'mac'),
        ('network', 'network'), ('next', 'next'),
        ('none', 'none'), ('osf', 'osf'), ('printer', 'printer'),
        ('robot', 'robot'), ('solaris-2', 'solaris-2'),
        ('sun4', 'sun4'), ('unknown', 'unknown'), ('virtual', 'virtual'),
        ('win31', 'win31'), ('win95', 'win95'),
        ('winNTs', 'winNTs'), ('winNTw', 'winNTw'),
        ('win2k', 'win2k'), ('winXP', 'winXP'), ('xterm', 'xterm')
        )
    hostname = models.CharField(max_length=64)
    whatami = models.CharField(max_length=16)
    netgroup = models.CharField(max_length=32, choices=NETGROUP_CHOICES)
    security_class = models.CharField('class', max_length=16)
    support = models.CharField(max_length=8, choices=SUPPORT_CHOICES)
    csi = models.CharField(max_length=32, blank=True)
    printq = models.CharField(max_length=32, blank=True)
    outbound_smtp = models.BooleanField()
    primary_user = models.EmailField()
    administrator = models.EmailField(blank=True)
    location = models.CharField(max_length=16)
    comments = models.TextField(blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    last = models.DateField(auto_now=True, auto_now_add=True)
    status = models.CharField(max_length=7, choices=STATUS_CHOICES)
    dirty = models.BooleanField()

    class Admin:
        list_display = ('hostname', 'last')
        search_fields = ['hostname']

    def __str__(self):
        return self.hostname

    def get_logs(self):
        """
            Get host's log.
        """
        return Log.objects.filter(hostname=self.hostname)

class Interface(models.Model):
    TYPE_CHOICES = (
        ('eth', 'ethernet'), ('wl', 'wireless'), ('virtual', 'virtual'), ('myr', 'myr'),
        ('mgmt', 'mgmt'), ('tape', 'tape'), ('fe', 'fe'), ('ge', 'ge'),
        )
    # FIXME: The new admin interface has change a lot.
    #host = models.ForeignKey(Host, edit_inline=models.TABULAR, num_in_admin=2)
    host = models.ForeignKey(Host)
    # FIXME: The new admin interface has change a lot.
    #mac_addr = models.CharField(max_length=32, core=True)
    mac_addr = models.CharField(max_length=32)
    hdwr_type = models.CharField('type', max_length=16, choices=TYPE_CHOICES, blank=True)
    # FIXME: The new admin interface has change a lot.
    #                             radio_admin=True, blank=True)
    dhcp = models.BooleanField()

    def __str__(self):
        return self.mac_addr

    class Admin:
        list_display = ('mac_addr', 'host')
        search_fields = ['mac_addr']

class IP(models.Model):
    interface = models.ForeignKey(Interface)
    # FIXME: The new admin interface has change a lot.
    #                              edit_inline=models.TABULAR, num_in_admin=1)
    #ip_addr = models.IPAddressField(core=True)
    ip_addr = models.IPAddressField()

    def __str__(self):
        return self.ip_addr

    class Admin:
        pass

    class Meta:
        ordering = ('ip_addr', )

class MX(models.Model):
    priority = models.IntegerField(blank=True)
    # FIXME: The new admin interface has change a lot.
    #mx = models.CharField(max_length=64, blank=True, core=True)
    mx = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return (" ".join([str(self.priority), self.mx]))

    class Admin:
        pass

class Name(models.Model):
    DNS_CHOICES = (
        ('global','global'),('internal','ANL internal'),
        ('private','private')
        )
    # FIXME: The new admin interface has change a lot.
    #ip = models.ForeignKey(IP, edit_inline=models.TABULAR, num_in_admin=1)
    ip = models.ForeignKey(IP)
    # FIXME: The new admin interface has change a lot.
    #name = models.CharField(max_length=64, core=True)
    name = models.CharField(max_length=64)
    dns_view = models.CharField(max_length=16, choices=DNS_CHOICES)
    only = models.BooleanField(blank=True)
    mxs = models.ManyToManyField(MX)

    def __str__(self):
        return self.name

    class Admin:
        pass

class CName(models.Model):
    # FIXME: The new admin interface has change a lot.
    #name = models.ForeignKey(Name, edit_inline=models.TABULAR, num_in_admin=1)
    name = models.ForeignKey(Name)
    # FIXME: The new admin interface has change a lot.
    #cname = models.CharField(max_length=64, core=True)
    cname = models.CharField(max_length=64)

    def __str__(self):
        return self.cname

    class Admin:
        pass

class Nameserver(models.Model):
    name = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.name

    class Admin:
        pass

class ZoneAddress(models.Model):
    ip_addr = models.IPAddressField(blank=True)

    def __str__(self):
        return self.ip_addr

    class Admin:
        pass

class Zone(models.Model):
    zone = models.CharField(max_length=64)
    serial = models.IntegerField()
    admin = models.CharField(max_length=64)
    primary_master = models.CharField(max_length=64)
    expire = models.IntegerField()
    retry = models.IntegerField()
    refresh = models.IntegerField()
    ttl = models.IntegerField()
    nameservers = models.ManyToManyField(Nameserver, blank=True)
    mxs = models.ManyToManyField(MX, blank=True)
    addresses = models.ManyToManyField(ZoneAddress, blank=True)
    aux = models.TextField(blank=True)

    def __str__(self):
        return self.zone

    class Admin:
        pass

class Log(models.Model):
    # FIXME: Proposal hostname = models.ForeignKey(Host)
    hostname = models.CharField(max_length=64)
    date = models.DateTimeField(auto_now=True, auto_now_add=True)
    log = models.TextField()

    def __str__(self):
        return self.hostname

class ZoneLog(models.Model):
    zone = models.CharField(max_length=64)
    date = models.DateTimeField(auto_now=True, auto_now_add=True)
    log = models.TextField()

    def __str__(self):
        return self.zone
