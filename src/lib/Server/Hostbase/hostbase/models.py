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
        ('linux-rh80', 'linux-rh80'), ('linux-sles80', 'linux-sles80'),
        ('linux-sles80-64', 'linux-sles80-64'), ('linux-sles80-ia32', 'linux-sles80-ia32'),
        ('linux-sles80-ia64', 'linux-sles80-ia64'), ('mac', 'mac'),
        ('network', 'network'), ('next', 'next'),
        ('none', 'none'), ('osf', 'osf'), ('printer', 'printer'),
        ('robot', 'robot'), ('solaris-2', 'solaris-2'),
        ('sun4', 'sun4'), ('unknown', 'unknown'), ('virtual', 'virtual'),
        ('win31', 'win31'), ('win95', 'win95'),
        ('winNTs', 'winNTs'), ('winNTw', 'winNTw'),
        ('win2k', 'win2k'), ('winXP', 'winXP'), ('xterm', 'xterm')
        )
    hostname = models.CharField(maxlength=64)
    whatami = models.CharField(maxlength=16)
    netgroup = models.CharField(maxlength=32, choices=NETGROUP_CHOICES)
    security_class = models.CharField('class', maxlength=16)
    support = models.CharField(maxlength=8, choices=SUPPORT_CHOICES)
    csi = models.CharField(maxlength=32, blank=True)
    printq = models.CharField(maxlength=32)
    dhcp = models.BooleanField()
    outbound_smtp = models.BooleanField()
    primary_user = models.EmailField()
    administrator = models.EmailField(blank=True)
    location = models.CharField(maxlength=16)
    comments = models.TextField(blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    last = models.DateField(auto_now=True, auto_now_add=True)
    status = models.CharField(maxlength=7, choices=STATUS_CHOICES)

    class Admin:
        list_display = ('hostname', 'last')
        search_fields = ['hostname']

    def __str__(self):
        return self.hostname

class Interface(models.Model):
    TYPE_CHOICES = (
        ('eth', 'ethernet'), ('wl', 'wireless'), ('myr', 'myr'),
        ('mgmt', 'mgmt'), ('tape', 'tape'), ('fe', 'fe')
        )
    host = models.ForeignKey(Host, edit_inline=models.TABULAR, num_in_admin=2)
    mac_addr = models.CharField(maxlength=32, core=True)
    hdwr_type = models.CharField('type', maxlength=16, choices=TYPE_CHOICES,
                                 radio_admin=True, blank=True)
    
    def __str__(self):
        return self.mac_addr

    class Admin:
        list_display = ('mac_addr', 'host')
        search_fields = ['mac_addr']

class IP(models.Model):
    interface = models.ForeignKey(Interface,
                                  edit_inline=models.TABULAR, num_in_admin=1)
    ip_addr = models.IPAddressField(core=True)
    num = models.IntegerField()
    
    def __str__(self):
        return self.ip_addr

    class Admin:
        pass

    class Meta:
        ordering = ('ip_addr', )

class MX(models.Model):
    priority = models.IntegerField()
    mx = models.CharField(maxlength=64, core=True)

    def __str__(self):
        return (" ".join([str(self.priority), self.mx]))

    class Admin:
        pass

class Name(models.Model):
    DNS_CHOICES = (
        ('global','global'),('internal','ANL internal'),
        ('mcs-internal','MCS internal'),('private','private')
        )
    ip = models.ForeignKey(IP, edit_inline=models.TABULAR, num_in_admin=1)
    name = models.CharField(maxlength=64, core=True)
    dns_view = models.CharField(maxlength=16, choices=DNS_CHOICES)
    only = models.BooleanField(blank=True)
    mxs = models.ManyToManyField(MX)

    def __str__(self):
        return self.name
    
    class Admin:
        pass

class CName(models.Model):
    name = models.ForeignKey(Name, edit_inline=models.TABULAR, num_in_admin=1)
    cname = models.CharField(maxlength=64, core=True)

    def __str__(self):
        return self.cname

    class Admin:
        pass

class Nameserver(models.Model):
    name = models.CharField(maxlength=64)

    def __str__(self):
        return self.name

    class Admin:
        pass

class Zone(models.Model):
    zone = models.CharField(maxlength=64)
    serial = models.IntegerField()
    admin = models.CharField(maxlength=64)
    primary_master = models.CharField(maxlength=64)
    expire = models.IntegerField()
    retry = models.IntegerField()
    refresh = models.IntegerField()
    ttl = models.IntegerField()
    nameservers = models.ManyToManyField(Nameserver)
    mxs = models.ManyToManyField(MX)
    addresses = models.ManyToManyField(IP, blank=True)
    aux = models.TextField(blank=True)

    def __str__(self):
        return self.zone

    class Admin:
        pass

