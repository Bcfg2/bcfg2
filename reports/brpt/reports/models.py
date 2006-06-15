from django.db import models
#from timedelta import timedelta
from datetime import datetime, timedelta
# Create your models here.
KIND_CHOICES = (
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
    name = models.CharField(maxlength=128)
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
        if (self == self.client.interactions.order_by('-timestamp')[0]):#Is Mostrecent
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
                

    class Admin:
        list_display = ('client', 'timestamp', 'state')
        list_filter = ['client', 'timestamp']
        pass
    



class Modified(models.Model):
    interaction = models.ForeignKey(Interaction, related_name="modified_items", edit_inline=models.STACKED)
    name = models.CharField(maxlength=128, core=True)#name of modified thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    how = models.CharField(maxlength=256)
    def __str__(self):
        return self.name
 

    
class Extra(models.Model):
    interaction = models.ForeignKey(Interaction, related_name="extra_items", edit_inline=models.STACKED)
    name = models.CharField(maxlength=128, core=True)#name of Extra thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    why = models.CharField(maxlength=256)#current state of some thing...
    def __str__(self):
        return self.name
 

    
class Bad(models.Model):
    interaction = models.ForeignKey(Interaction, related_name="bad_items", edit_inline=models.STACKED)
    name = models.CharField(maxlength=128, core=True)#name of bad thing.
    kind = models.CharField(maxlength=16, choices=KIND_CHOICES)#Service/Package/ConfgFile...
    reason = models.CharField(maxlength=256)#that its bad...
    def __str__(self):
        return self.name
 

#performance metrics, models a performance-metric-item
class Performance(models.Model):
    interaction = models.ForeignKey(Interaction, related_name="performance_items", edit_inline=models.STACKED)
    metric = models.CharField(maxlength=128, core=True)
    value = models.FloatField(max_digits=32, decimal_places=16)
    def __str__(self):
        return self.metric
 

 
