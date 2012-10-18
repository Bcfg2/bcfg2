"""Helper functions for reports"""
from django.conf.urls.defaults import *
import re

"""List of filters provided by filteredUrls"""
filter_list = ('server', 'state', 'group')


class BatchFetch(object):
    """Fetch Django objects in smaller batches to save memory"""

    def __init__(self, obj, step=10000):
        self.count = 0
        self.block_count = 0
        self.obj = obj
        self.data = None
        self.step = step
        self.max = obj.count()

    def __iter__(self):
        return self

    def next(self):
        """Provide compatibility with python < 3.0"""
        return self.__next__()

    def __next__(self):
        """Return the next object from our array and fetch from the
           database when needed"""
        if self.block_count + self.count - self.step == self.max:
            raise StopIteration
        if self.block_count == 0 or self.count == self.step:
            # Without list() this turns into LIMIT 1 OFFSET x queries
            self.data = list(self.obj.all()[self.block_count: \
                                   (self.block_count + self.step)])
            self.block_count += self.step
            self.count = 0
        self.count += 1
        return self.data[self.count - 1]


def generateUrls(fn):
    """
    Parse url tuples and send to functions.

    Decorator for url generators.  Handles url tuple parsing
    before the actual function is called.
    """
    def url_gen(*urls):
        results = []
        for url_tuple in urls:
            if isinstance(url_tuple, (list, tuple)):
                results += fn(*url_tuple)
            else:
                raise ValueError("Unable to handle compiled urls")
        return results
    return url_gen


@generateUrls
def paginatedUrls(pattern, view, kwargs=None, name=None):
    """
    Takes a group of url tuples and adds paginated urls.

    Extends a url tuple to include paginated urls.
    Currently doesn't handle url() compiled patterns.

    """
    results = [(pattern, view, kwargs, name)]
    tail = ''
    mtail = re.search('(/+\+?\\*?\??\$?)$', pattern)
    if mtail:
        tail = mtail.group(1)
    pattern = pattern[:len(pattern) - len(tail)]
    results += [(pattern + "/(?P<page_number>\d+)" + tail, view, kwargs)]
    results += [(pattern + "/(?P<page_number>\d+)\|(?P<page_limit>\d+)" +
                 tail, view, kwargs)]
    if not kwargs:
        kwargs = dict()
    kwargs['page_limit'] = 0
    results += [(pattern + "/?\|(?P<page_limit>all)" + tail, view, kwargs)]
    return results


@generateUrls
def filteredUrls(pattern, view, kwargs=None, name=None):
    """
    Takes a url and adds filtered urls.

    Extends a url tuple to include filtered view urls.  Currently doesn't
    handle url() compiled patterns.
    """
    results = [(pattern, view, kwargs, name)]
    tail = ''
    mtail = re.search('(/+\+?\\*?\??\$?)$', pattern)
    if mtail:
        tail = mtail.group(1)
    pattern = pattern[:len(pattern) - len(tail)]
    for filter in ('/state/(?P<state>\w+)',
                   '/group/(?P<group>[\w\-\.]+)',
                   '/group/(?P<group>[\w\-\.]+)/(?P<state>[A-Za-z]+)',
                   '/server/(?P<server>[\w\-\.]+)',
                   '/server/(?P<server>[\w\-\.]+)/(?P<state>[A-Za-z]+)',
                   '/server/(?P<server>[\w\-\.]+)/group/(?P<group>[\w\-\.]+)',
                   '/server/(?P<server>[\w\-\.]+)/group/(?P<group>[\w\-\.]+)/(?P<state>[A-Za-z]+)'):
        results += [(pattern + filter + tail, view, kwargs)]
    return results


@generateUrls
def timeviewUrls(pattern, view, kwargs=None, name=None):
    """
    Takes a url and adds timeview urls

    Extends a url tuple to include filtered view urls.  Currently doesn't
    handle url() compiled patterns.
    """
    results = [(pattern, view, kwargs, name)]
    tail = ''
    mtail = re.search('(/+\+?\\*?\??\$?)$', pattern)
    if mtail:
        tail = mtail.group(1)
    pattern = pattern[:len(pattern) - len(tail)]
    for filter in ('/(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})/' + \
                       '(?P<hour>\d\d)-(?P<minute>\d\d)',
                   '/(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})'):
        results += [(pattern + filter + tail, view, kwargs)]
    return results
