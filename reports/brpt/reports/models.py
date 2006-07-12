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

    '''returns most recent interaction as of specified timestamp in format:
    '2006-01-01 00:00:00' or 'now' or None->'now'  '''
    def interaction_per_client(self, maxdate = None):
        from django.db import connection
        cursor = connection.cursor()
        if (maxdate == 'now' or maxdate == None): 
            cursor.execute("select reports_interaction.id, x.client_id from (select client_id, MAX(timestamp) "+
                           "as timer from reports_interaction GROUP BY client_id) x, reports_interaction where "+
                           "reports_interaction.client_id = x.client_id AND reports_interaction.timestamp = x.timer")
        else:
            cursor.execute("select reports_interaction.id, x.client_id from (select client_id, timestamp, MAX(timestamp) "+
                           "as timer from reports_interaction WHERE timestamp < %s GROUP BY client_id) x, reports_interaction where "+
                           "reports_interaction.client_id = x.client_id AND reports_interaction.timestamp = x.timer", [maxdate])

#            cursor.execute("select id, client_id, timestamp, MAX(timestamp) AS maxtimestamp from reports_interaction where timestamp < %s GROUP BY client_id", [maxdate])
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
        if not self.totalcount == 0:
            return (self.goodcount/self.totalcount)*100
        else:
            return 0

    def percentbad(self):
        if not self.totalcount == 0:
            return (self.totalcount-self.goodcount)/(self.totalcount)
        else:
            return 0
    
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

class Reason(models.Model):
    owner = models.TextField(maxlength=128, blank=True)
    current_owner = models.TextField(maxlength=128, blank=True)
    group = models.TextField(maxlength=128, blank=True)
    current_group = models.TextField(maxlength=128, blank=True)
    perms =  models.TextField(maxlength=4, blank=True)#because permissions might start with zero, and the db might think its octal and break
    current_perms = models.TextField(maxlength=4,blank=True)
    status = models.TextField(maxlength=3, blank=True)#on/off/(None)
    current_status = models.TextField(maxlength=1, blank=True)#on/off/(None)
    to = models.TextField(maxlength=256, blank=True)
    current_to = models.TextField(maxlength=256, blank=True)
    version = models.TextField(maxlength=128, blank=True)
    current_version = models.TextField(maxlength=128, blank=True)
    current_exists = models.BooleanField()#False means its missing!, only display if its False, true is default..
    current_diff = models.TextField(maxlength=1280, blank=True) #diff
    def _str_(self):
        return "Reason"

class Modified(models.Model):
    interactions = models.ManyToManyField(Interaction, related_name="modified_items")
    name = models.CharField(maxlength=128, core=True)#name of modified thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    critical = models.BooleanField()
    reason = models.ForeignKey(Reason)
    def __str__(self):
        return self.name
   
class Extra(models.Model):
    interactions = models.ManyToManyField(Interaction, related_name="extra_items")
    name = models.CharField(maxlength=128, core=True)#name of Extra thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    critical = models.BooleanField()
    reason = models.ForeignKey(Reason)
    def __str__(self):
        return self.name
    
class Bad(models.Model):
    interactions = models.ManyToManyField(Interaction, related_name="bad_items")
    name = models.CharField(maxlength=128, core=True)#name of bad thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    critical = models.BooleanField()
    reason = models.ForeignKey(Reason)
    def __str__(self):
        return self.name
 
class PerformanceManager(models.Manager):

    #Date format for maxdate: '2006-01-01 00:00:00'            
    def performance_per_client(self, maxdate = None):
        from django.db import connection
        cursor = connection.cursor()
        if (maxdate == 'now' or maxdate == None):
            cursor.execute("SELECT reports_client.name, reports_performance.metric, reports_performance.value "+
            "FROM reports_performance, reports_performance_interaction, reports_client WHERE ( "+
            "reports_client.current_interaction_id = reports_performance_interaction.interaction_id AND "+
            "reports_performance.id = reports_performance_interaction.performance_id)")
        else:
            cursor.execute("select reports_client.name, reports_performance.metric, "+
                           "reports_performance.value from (Select reports_interaction.client_id as client_id, "+
                           "MAX(reports_interaction.timestamp) as timestamp from reports_interaction where "+
                           "timestamp < %s GROUP BY reports_interaction.client_id) x, reports_client, "+
                           "reports_interaction, reports_performance, reports_performance_interaction where "+
                           "reports_client.id = x.client_id AND x.timestamp = reports_interaction.timestamp AND "+
                           "x.client_id = reports_interaction.client_id AND reports_performance.id = "+
                           "reports_performance_interaction.performance_id AND "+
                           "reports_performance_interaction.interaction_id = reports_interaction.id", [maxdate])

        results = {}
        for row in cursor.fetchall():
            try:
                results[row[0]].__setitem__(row[1],row[2])
            except KeyError:
                results[row[0]] = {row[1]:row[2]}
                                
        return results
    
#performance metrics, models a performance-metric-item
class Performance(models.Model):
    interaction = models.ManyToManyField(Interaction, related_name="performance_items")
    metric = models.CharField(maxlength=128, core=True)
    value = models.FloatField(max_digits=32, decimal_places=16)
    def __str__(self):
        return self.metric
 
    objects = PerformanceManager()
 
