from django.db import models
#from timedelta import timedelta
from datetime import datetime, timedelta
# Create your models here.
KIND_CHOICES = (
    #These are the kinds of config elements
    ('ConfigFile', 'ConfigFile'),
    ('Package', 'Package'),
    ('Service', 'Service'),
    ('SymLink', 'SymLink'),
    ('Directory', 'Directory'),
    ('Permissions','Permissions'),
)
REASON_CHOICES = (
    #these are the possible reasons there can be a problem with a node:
    ('', 'No Reason'),
    ('O','Owner'),
    ('P','Permissions'),
    ('E','Existence'),
    ('C','Content'),
    ('OP','Owner, Permissions'),
    ('OE','Owner, Existence'),
    ('OC','Owner, Content'),
    ('PE','Permissions, Existence'),
    ('PC','Permissions, Content'),
    ('EC','Existence, Content'),
    ('OPE','Owner, Permissions, Existence'),
    ('OPC','Owner, Permissions, Content'),
    ('OEC','Owner, Existence, Content'),
    ('PEC','Permissions, Existence, Content'),
    ('OPEC','Owner, Permissions, Existence, Content'),
)
class Client(models.Model):
    #This exists for clients that are no longer in the repository even! (timeless)
    creation = models.DateTimeField()
    name = models.CharField(maxlength=128, core=True)
    current_interaction = models.ForeignKey('Interaction', null=True,blank=True, related_name="parent_client")
    
    def __str__(self):
        return self.name

    class Admin:
        pass


class Metadata(models.Model):
    client = models.ForeignKey(Client)
    timestamp = models.DateTimeField()
    #INSERT magic interface to Metadata HERE
    def __str__(self):
        return self.timestamp
    
class Repository(models.Model):
    timestamp = models.DateTimeField()
    #INSERT magic interface to any other config info here...
    def __str__(self):
        return self.timestamp

class InteractiveManager(models.Manager):
    def interaction_per_client(self, maxdate):
        from django.db import connection
        cursor = connection.cursor()
        if maxdate == 'now':
            cursor.execute("select id, client_id, MAX(timestamp) AS maxtimestamp from reports_interaction GROUP BY client_id")
        else:
            cursor.execute("select id, client_id, timestamp, MAX(timestamp) AS maxtimestamp from reports_interaction where timestamp < %s GROUP BY client_id", [maxdate])
        #rows = cursor.fetchall()
        #return rows
        in_idents = [item[0] for item in cursor.fetchall()]
        return self.filter(id__in = in_idents)

        '2006-01-01 00:00:00'

#models each client-interaction
class Interaction(models.Model):
    client = models.ForeignKey(Client, related_name="interactions", core=True)
    timestamp = models.DateTimeField()#Timestamp for this record
    state = models.CharField(maxlength=32)#good/bad/modified/etc
    repo_revision = models.IntegerField()#you got it. the repo in use at time of client interaction
    client_version = models.CharField(maxlength=32)#really simple; version of client running
    pingable = models.BooleanField()#This is (was-pingable)status as of last attempted interaction
    goodcount = models.IntegerField()#of good config-items we store this number, because we don't count the
    totalcount = models.IntegerField()#of total config-items specified--grab this from metadata instead?

    def __str__(self):
        return "With " + self.client.name + " @ " + self.timestamp.isoformat()

    def percentgood(self):
        return (self.goodcount/self.totalcount)*100

    def percentbad(self):
        return (self.totalcount-self.goodcount)/(self.totalcount)
    
    def isclean(self):
        if (self.bad_items.count() == 0 and self.extra_items.count() == 0 and self.goodcount == self.totalcount):
        #if (self.state == "good"):
            return True
        else:
            return False
        
    def isstale(self):
        if (self == self.client.current_interaction):#Is Mostrecent
            if(datetime.now()-self.timestamp > timedelta(hours=25) ):
                return True
            else:
                return False
        else:
            #Search for subsequent Interaction for this client
            #Check if it happened more than 25 hrs ago.
            if (self.client.interactions.filter(timestamp__gt=self.timestamp)
                .order_by('timestamp')[0].timestamp - self.timestamp > timedelta(hours=25)):
                return True
            else:
                return False
    def save(self):
        super(Interaction,self).save() #call the real save...
        self.client.current_interaction = self.client.interactions.latest()
        self.client.save()#do i need to save the self.client manually?
            
    objects = InteractiveManager()

    class Admin:
        list_display = ('client', 'timestamp', 'state')
        list_filter = ['client', 'timestamp']
        pass
    class Meta:
        get_latest_by = 'timestamp'


class Modified(models.Model):
    interactions = models.ManyToManyField(Interaction, related_name="modified_items")
    name = models.CharField(maxlength=128, core=True)#name of modified thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    problemcode = models.CharField(maxlength=8, choices=REASON_CHOICES)
    reason = models.TextField(maxlength=1280)
    def __str__(self):
        return self.name
 

    
class Extra(models.Model):
    interactions = models.ManyToManyField(Interaction, related_name="extra_items")
    name = models.CharField(maxlength=128, core=True)#name of Extra thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    problemcode = models.CharField(maxlength=8, choices=REASON_CHOICES)
    reason = models.TextField(maxlength=1280)
    def __str__(self):
        return self.name
 

    
class Bad(models.Model):
    interactions = models.ManyToManyField(Interaction, related_name="bad_items")
    name = models.CharField(maxlength=128, core=True)#name of bad thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    problemcode = models.CharField(maxlength=8, choices=REASON_CHOICES)
    reason = models.TextField(maxlength=1280)
    def __str__(self):
        return self.name
 

#performance metrics, models a performance-metric-item
class Performance(models.Model):
    interaction = models.ManyToManyField(Interaction, related_name="performance_items")
    metric = models.CharField(maxlength=128, core=True)
    value = models.FloatField(max_digits=32, decimal_places=16)
    def __str__(self):
        return self.metric
 

 
