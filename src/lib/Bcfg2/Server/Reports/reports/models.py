"""Django models for Bcfg2 reports."""
import sys

from django.core.exceptions import ImproperlyConfigured
try:
    from django.db import models
except ImproperlyConfigured:
    e = sys.exc_info()[1]
    print("Reports: unable to import django models: %s" % e)
    sys.exit(1)

from django.db import connection, transaction
from django.db.models import Q
from datetime import datetime, timedelta
from time import strptime

KIND_CHOICES = (
    #These are the kinds of config elements
    ('Package', 'Package'),
    ('Path', 'directory'),
    ('Path', 'file'),
    ('Path', 'permissions'),
    ('Path', 'symlink'),
    ('Service', 'Service'),
)
TYPE_GOOD = 0
TYPE_BAD = 1
TYPE_MODIFIED = 2
TYPE_EXTRA = 3

TYPE_CHOICES = (
    (TYPE_GOOD, 'Good'),
    (TYPE_BAD, 'Bad'),
    (TYPE_MODIFIED, 'Modified'),
    (TYPE_EXTRA, 'Extra'),
)


def convert_entry_type_to_id(type_name):
    """Convert a entry type to its entry id"""
    for e_id, e_name in TYPE_CHOICES:
        if e_name.lower() == type_name.lower():
            return e_id
    return -1


class ClientManager(models.Manager):
    """Extended client manager functions."""
    def active(self, timestamp=None):
        """returns a set of clients that have been created and have not
        yet been expired as of optional timestmamp argument. Timestamp
        should be a datetime object."""

        if timestamp == None:
            timestamp = datetime.now()
        elif not isinstance(timestamp, datetime):
            raise ValueError('Expected a datetime object')
        else:
            try:
                timestamp = datetime(*strptime(timestamp,
                                               "%Y-%m-%d %H:%M:%S")[0:6])
            except ValueError:
                return self.none()

        return self.filter(Q(expiration__gt=timestamp) | Q(expiration__isnull=True),
                           creation__lt=timestamp)


class Client(models.Model):
    """Object representing every client we have seen stats for."""
    creation = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=128,)
    current_interaction = models.ForeignKey('Interaction',
                                            null=True, blank=True,
                                            related_name="parent_client")
    expiration = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name

    objects = ClientManager()

    class Admin:
        pass


class InteractiveManager(models.Manager):
    """Manages interactions objects."""

    def interaction_per_client(self, maxdate=None, active_only=True):
        """
        Returns the most recent interactions for clients as of a date

        Arguments:
        maxdate -- datetime object.  Most recent date to pull. (dafault None)
        active_only -- Include only active clients (default True)

        """

        if maxdate and not isinstance(maxdate, datetime):
            raise ValueError('Expected a datetime object')
        return self.filter(id__in=self.get_interaction_per_client_ids(maxdate, active_only))

    def get_interaction_per_client_ids(self, maxdate=None, active_only=True):
        """
        Returns the ids of most recent interactions for clients as of a date.

        Arguments:
        maxdate -- datetime object.  Most recent date to pull. (dafault None)
        active_only -- Include only active clients (default True)

        """
        from django.db import connection
        cursor = connection.cursor()
        cfilter = "expiration is null"

        sql = 'select reports_interaction.id, x.client_id from (select client_id, MAX(timestamp) ' + \
                    'as timer from reports_interaction'
        if maxdate:
            if not isinstance(maxdate, datetime):
                raise ValueError('Expected a datetime object')
            sql = sql + " where timestamp <= '%s' " % maxdate
            cfilter = "(expiration is null or expiration > '%s') and creation <= '%s'" % (maxdate, maxdate)
        sql = sql + ' GROUP BY client_id) x, reports_interaction where ' + \
                    'reports_interaction.client_id = x.client_id AND reports_interaction.timestamp = x.timer'
        if active_only:
            sql = sql + " and x.client_id in (select id from reports_client where %s)" % \
                cfilter
        try:
            cursor.execute(sql)
            return [item[0] for item in cursor.fetchall()]
        except:
            '''FIXME - really need some error handling'''
            pass
        return []


class Interaction(models.Model):
    """Models each reconfiguration operation interaction between client and server."""
    client = models.ForeignKey(Client, related_name="interactions")
    timestamp = models.DateTimeField(db_index=True)  # Timestamp for this record
    state = models.CharField(max_length=32)  # good/bad/modified/etc
    repo_rev_code = models.CharField(max_length=64)  # repo revision at time of interaction
    goodcount = models.IntegerField()  # of good config-items
    totalcount = models.IntegerField()  # of total config-items
    server = models.CharField(max_length=256)  # Name of the server used for the interaction
    bad_entries = models.IntegerField(default=-1)
    modified_entries = models.IntegerField(default=-1)
    extra_entries = models.IntegerField(default=-1)

    def __str__(self):
        return "With " + self.client.name + " @ " + self.timestamp.isoformat()

    def percentgood(self):
        if not self.totalcount == 0:
            return (self.goodcount / float(self.totalcount)) * 100
        else:
            return 0

    def percentbad(self):
        if not self.totalcount == 0:
            return ((self.totalcount - self.goodcount) / (float(self.totalcount))) * 100
        else:
            return 0

    def isclean(self):
        if (self.bad_entry_count() == 0 and self.goodcount == self.totalcount):
            return True
        else:
            return False

    def isstale(self):
        if (self == self.client.current_interaction):  # Is Mostrecent
            if(datetime.now() - self.timestamp > timedelta(hours=25)):
                return True
            else:
                return False
        else:
            #Search for subsequent Interaction for this client
            #Check if it happened more than 25 hrs ago.
            if (self.client.interactions.filter(timestamp__gt=self.timestamp)
                    .order_by('timestamp')[0].timestamp -
                    self.timestamp > timedelta(hours=25)):
                return True
            else:
                return False

    def save(self):
        super(Interaction, self).save()  # call the real save...
        self.client.current_interaction = self.client.interactions.latest()
        self.client.save()  # save again post update

    def delete(self):
        '''Override the default delete.  Allows us to remove Performance items'''
        pitems = list(self.performance_items.all())
        super(Interaction, self).delete()
        for perf in pitems:
            if perf.interaction.count() == 0:
                perf.delete()

    def badcount(self):
        return self.totalcount - self.goodcount

    def bad(self):
        return Entries_interactions.objects.select_related().filter(interaction=self, type=TYPE_BAD)

    def bad_entry_count(self):
        """Number of bad entries.  Store the count in the interation field to save db queries."""
        if self.bad_entries < 0:
            self.bad_entries = Entries_interactions.objects.filter(interaction=self, type=TYPE_BAD).count()
            self.save()
        return self.bad_entries

    def modified(self):
        return Entries_interactions.objects.select_related().filter(interaction=self, type=TYPE_MODIFIED)

    def modified_entry_count(self):
        """Number of modified entries.  Store the count in the interation field to save db queries."""
        if self.modified_entries < 0:
            self.modified_entries = Entries_interactions.objects.filter(interaction=self, type=TYPE_MODIFIED).count()
            self.save()
        return self.modified_entries

    def extra(self):
        return Entries_interactions.objects.select_related().filter(interaction=self, type=TYPE_EXTRA)

    def extra_entry_count(self):
        """Number of extra entries.  Store the count in the interation field to save db queries."""
        if self.extra_entries < 0:
            self.extra_entries = Entries_interactions.objects.filter(interaction=self, type=TYPE_EXTRA).count()
            self.save()
        return self.extra_entries

    objects = InteractiveManager()

    class Admin:
        list_display = ('client', 'timestamp', 'state')
        list_filter = ['client', 'timestamp']
        pass

    class Meta:
        get_latest_by = 'timestamp'
        ordering = ['-timestamp']
        unique_together = ("client", "timestamp")


class Reason(models.Model):
    """reason why modified or bad entry did not verify, or changed."""
    owner = models.CharField(max_length=255, blank=True)
    current_owner = models.CharField(max_length=255, blank=True)
    group = models.CharField(max_length=255, blank=True)
    current_group = models.CharField(max_length=255, blank=True)
    perms = models.CharField(max_length=4, blank=True)
    current_perms = models.CharField(max_length=4, blank=True)
    status = models.CharField(max_length=128, blank=True)
    current_status = models.CharField(max_length=128, blank=True)
    to = models.CharField(max_length=1024, blank=True)
    current_to = models.CharField(max_length=1024, blank=True)
    version = models.CharField(max_length=1024, blank=True)
    current_version = models.CharField(max_length=1024, blank=True)
    current_exists = models.BooleanField()  # False means its missing. Default True
    current_diff = models.TextField(max_length=1024*1024, blank=True)
    is_binary = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    unpruned = models.TextField(max_length=4096, blank=True, default='')

    def _str_(self):
        return "Reason"

    def short_list(self):
        rv = []
        if self.current_owner or self.current_group or self.current_perms:
            rv.append("File permissions")
        if self.current_status:
            rv.append("Incorrect status")
        if self.current_to:
            rv.append("Incorrect target")
        if self.current_version or self.version == 'auto':
            rv.append("Wrong version")
        if not self.current_exists:
            rv.append("Missing")
        if self.current_diff or self.is_sensitive:
            rv.append("Incorrect data")
        if self.unpruned:
            rv.append("Directory has extra files")
        if len(rv) == 0:
            rv.append("Exists")
        return rv

    @staticmethod
    @transaction.commit_on_success
    def prune_orphans():
        '''Prune oprhaned rows... no good way to use the ORM'''
        cursor = connection.cursor()
        cursor.execute('delete from reports_reason where not exists (select rei.id from reports_entries_interactions rei where rei.reason_id = reports_reason.id)')
        transaction.set_dirty()


class Entries(models.Model):
    """Contains all the entries feed by the client."""
    name = models.CharField(max_length=128, db_index=True)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, db_index=True)

    def __str__(self):
        return self.name

    @staticmethod
    @transaction.commit_on_success
    def prune_orphans():
        '''Prune oprhaned rows... no good way to use the ORM'''
        cursor = connection.cursor()
        cursor.execute('delete from reports_entries where not exists (select rei.id from reports_entries_interactions rei where rei.entry_id = reports_entries.id)')
        transaction.set_dirty()

    class Meta:
        unique_together = ("name", "kind")


class Entries_interactions(models.Model):
    """Define the relation between the reason, the interaction and the entry."""
    entry = models.ForeignKey(Entries)
    reason = models.ForeignKey(Reason)
    interaction = models.ForeignKey(Interaction)
    type = models.IntegerField(choices=TYPE_CHOICES)


class Performance(models.Model):
    """Object representing performance data for any interaction."""
    interaction = models.ManyToManyField(Interaction, related_name="performance_items")
    metric = models.CharField(max_length=128)
    value = models.DecimalField(max_digits=32, decimal_places=16)

    def __str__(self):
        return self.metric

    @staticmethod
    @transaction.commit_on_success
    def prune_orphans():
        '''Prune oprhaned rows... no good way to use the ORM'''
        cursor = connection.cursor()
        cursor.execute('delete from reports_performance where not exists (select ri.id from reports_performance_interaction ri where ri.performance_id = reports_performance.id)')
        transaction.set_dirty()


class Group(models.Model):
    """
    Groups extracted from interactions

    name - The group name

    TODO - Most of this is for future use
    TODO - set a default group
    """

    name = models.CharField(max_length=255, unique=True)
    profile = models.BooleanField(default=False)
    public = models.BooleanField(default=False)
    category = models.CharField(max_length=1024, blank=True)
    comment = models.TextField(blank=True)

    groups = models.ManyToManyField("self", symmetrical=False)
    bundles = models.ManyToManyField("Bundle")

    def __unicode__(self):
        return self.name


class Bundle(models.Model):
    """
    Bundles extracted from interactions

    name - The bundle name
    """

    name = models.CharField(max_length=255, unique=True)

    def __unicode__(self):
        return self.name


class InteractionMetadata(models.Model):
    """
    InteractionMetadata

    Hold extra data associated with the client and interaction
    """

    interaction = models.OneToOneField(Interaction, primary_key=True, related_name='metadata')
    profile = models.ForeignKey(Group, related_name="+")
    groups = models.ManyToManyField(Group)
    bundles = models.ManyToManyField(Bundle)


