#!/usr/bin/env python

#Jun 7 2005
#StatReports
'''Generates & distributes reports of statistic information for bcfg2'''

from ConfigParser import ConfigParser
from elementtree.ElementTree import *
from xml.parsers.expat import ExpatError
from xml.sax.saxutils import escape
from smtplib import SMTP
from time import asctime, strftime, strptime, ctime, gmtime
from socket import gethostbyname, gethostbyaddr, gaierror
from sys import exit, argv
from getopt import getopt, GetoptError
import re, string, os


def generatereport(report, delivery, deliverytype, statdata):
    '''generatereport creates and returns a report consisting
     list of tuples contining (title,body) pairs'''


    reportsections = []

    deliverytype = delivery.get("type", default = "nodes-individual")
    reportgood = report.get("good", default = 'Y')
    reportmodified = report.get("modified", default = 'Y')

    current_date = asctime()[:10]
    baddata = ''
    modified = ''
    msg = ''
    mheader = ''
    dirty = ''
    clean = ''


    '''build fqdn cache'''
    
    domain_list=['mcs.anl.gov', 'bgl.mcs.anl.gov', 'anchor.anl.gov', 'globus.org']
    fqdncache = {}
    allnodes = statdata.findall("Node") #this code is duplicated please remove...
    regex = string.join(map(lambda x:x.get("name"), report.findall('Machine')), '|')
    pattern = re.compile(regex)
    for node in allnodes:
        nodename = node.get("name")
        fqdncache[nodename] = ""
        if pattern.match(node.get("name")):
            for domain in domain_list:
                try:
                    fqdn = "%s.%s" % (nodename, domain)
                    ipaddr = gethostbyname(fqdn)
                    fqdncache[nodename] = fqdn
                    break
                except gaierror:
                    continue

        if fqdncache[nodename] == "":
            statdata.remove(node);
            del fqdncache[nodename]



    for machine in report.findall('Machine'):
        for node in statdata.findall('Node'):
            if node.attrib['name'] == machine.attrib['name']:
                if deliverytype == 'nodes-digest':
                    mheader = "Machine: %s\n" % machine.attrib['name']
                for stats in node.findall('Statistics'):
                    if stats.attrib['state'] == 'clean' \
                    and current_date in stats.attrib['time']:
                        clean += "%s\n" % machine.attrib['name']
                    if reportmodified == 'Y':
                        for modxml in stats.findall('Modified'):
                            if current_date in stats.attrib['time']:
                                modified += "\n%s\n" % tostring(modxml)
                    for bad in stats.findall('Bad'):
                        srtd = bad.findall('*')
                        srtd.sort(lambda x, y:cmp(tostring(x), tostring(y)))
                        strongbad = Element("Bad")
                        map(lambda x:strongbad.append(x), srtd)
                        baddata += "Time Ran:%s\n%s\n" % (stats.attrib['time'], tostring(strongbad))
                        dirty += "%s\n" % machine.attrib['name']
                        strongbad = ''
        if deliverytype == 'nodes-individual':
            if baddata != '':
                reportsections.append(("%s: Bcfg Nightly Errors" % machine.attrib['name'], \
                                       "%s%s" % (modified, baddata)))
            else:
                if reportgood == 'Y':
                    reportsections.append(("%s: Bcfg Nightly Good"%machine.attrib['name'], \
                                           "%s%s" % (modified, baddata)))
            baddata = ''
            modified = ''
        else:
            if not (modified == '' and baddata == ''):
                msg += "%s %s %s\n" % (mheader, modified, baddata)
            baddata = ''
            modified = ''

    if deliverytype == 'nodes-digest':
        if msg != '':
            reportsections.append(("Bcfg Nightly Errors", \
                                       "DIRTY:\n%s\nCLEAN:\n%s\nDETAILS:\n%s" % (dirty, clean, msg)))
        else:
            if report.attrib['good'] == 'Y':
                reportsections.append(("Bcfg Nightly All Machines Good", "All Machines Nomnial"))




    if deliverytype == 'overview-stats':
        children = statdata.findall("Node")
        regex = string.join(map(lambda x:x.get("name"), report.findall('Machine')), '|')
        pattern = re.compile(regex)
        childstates = []
        for child in children:
            if pattern.match(child.get("name")):
                child.states = []
                for state in child.findall("Statistics"):
                    child.states.append((child.get("name"), state.get("state"), state.get("time")))
                if child.states != []:
                    childstates.append(child.states[len(child.states)-1])
                    childstates.sort(lambda x, y:cmp(x[0], y[0]))

        staleones = []
        cleanones = []
        dirtyones = []
        unpingableones = []

        for instance in childstates:
            if instance[1] == "dirty":
                dirtyones.append(instance)
            elif instance[1] == "clean":
                cleanones.append(instance)
            if strptime(instance[2])[0] != strptime(ctime())[0] \
            or strptime(instance[2])[1] != strptime(ctime())[1] \
            or strptime(instance[2])[2] != strptime(ctime())[2]:
                staleones.append(instance)

        removableones = []
        
        #        if staleones != []:
        #            print "Pinging hosts that didn't run today. Please wait"
        for instance in staleones:
            if os.system( 'ping -c 1 ' + fqdncache[instance[0]] + ' &>/dev/null') != 0:
                removableones.append(instance)
                unpingableones.append(instance)


        for item in unpingableones:
            staleones.remove(item)

        statmsg = ''
        statmsg += "SUMMARY INFORMATION:\n"
        statmsg += "Up & Not Running Nightly:     %d\n" % len(staleones)
        statmsg += "Unpingable:                   %d\n" % len(unpingableones)
        statmsg += "Dirty:                        %d\n" % len(dirtyones)
        statmsg += "Clean:                        %d\n" % len(cleanones)
        statmsg += "---------------------------------\n"
        #total = len(cleanones) + len(dirtyones)
        statmsg += "Total:                        %d\n\n\n" % len(childstates)

        statmsg += "\n UP AND NOT RUNNING NIGHTLY:\n"
        for one in staleones:
            statmsg += fqdncache[one[0]] + "\n"
        statmsg += "\nDIRTY:\n"
        for one in dirtyones:
            statmsg += fqdncache[one[0]] + "\n"
        statmsg += "\nCLEAN:\n"
        for one in cleanones:
            statmsg += fqdncache[one[0]] + "\n"
        statmsg += "\nUNPINGABLE:\n"
        for one in unpingableones:
            statmsg += fqdncache[one[0]] + "\n"

        reportsections.append(("Bcfg Nightly Errors", "%s" % (statmsg)))

    return reportsections


def mail(reportsections, delivery):
    '''mail mails a previously generated report'''
    
    mailer = SMTP('localhost')
    fromaddr = "root@netzero.mcs.anl.gov"

    for destination in delivery.findall('Destination'):
        toaddr = destination.attrib['address']
        for section in reportsections:
            msg = "To: %s\nFrom: %s\nSubject: %s\n\n\n%s" % \
                  (toaddr, fromaddr, section[0], section[1])

            mailer.sendmail(fromaddr, toaddr, msg)
    mailer.quit()


def rss(reportsections, delivery, report):
    '''rss appends a new report to the specified rss file
     keeping the last 9 articles'''
    #check and see if rss file exists
    for destination in delivery.findall('Destination'):
        try:
            fil = open(destination.attrib['address'], 'r')
            olddoc = XML(fil.read())

            #defines the number of recent articles to keep
            items = olddoc.find("channel").findall("item")[0:9]
            fil.close()
            fil = open(destination.attrib['address'], 'w')
        except (IOError, ExpatError):
            fil = open(destination.attrib['address'], 'w')
            items = []

        rssdata = Element("rss")
        channel = SubElement(rss, "channel")
        rssdata.set("version", "2.0")
        chantitle = SubElement(channel, "title")
        chantitle.text = report.attrib['name']
        chanlink = SubElement(channel, "link")
        
        #this can later link to WWW report if one gets published simultaneously
        chanlink.text = "http://www.mcs.anl.gov/"
        chandesc = SubElement(channel, "description")
        chandesc.text = "Information regarding the 10 most recent bcfg2 runs."

        for section in reportsections:
            item = SubElement(channel, "item")
            title = SubElement(item, "title")
            title.text = section[0]
            description = SubElement(item, "description")
            description.text = "<pre>"+escape(section[1])+"</pre>"
            date = SubElement(item, "pubDate")
            date.text = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
            item = None
        if items != []:
            for item in items:
                channel.append(item)

        tree = "<?xml version=\"1.0\"?>" + tostring(rssdata)
        fil.write(tree)
        fil.close()

def www(reportsections, delivery):
    '''www outputs report to simple HTML'''
        
    #check and see if rss file xists
    for destination in delivery.findall('Destination'):
        fil = open(destination.attrib['address'], 'w')
        
        html = Element("HTML")
        body = SubElement(html, "BODY")
        for section in reportsections:
            SubElement(body, "br")
            item = SubElement(body, "div")
            title = SubElement(item, "h1")
            title.text = section[0]
            pre = SubElement(item, "pre")
            pre.text = section[1]
            SubElement(body, "hr")
            SubElement(body, "br")

        fil.write(tostring(html))
        fil.close()



if __name__ == '__main__':
    c = ConfigParser()
    c.read(['/etc/bcfg2.conf'])
    configpath = "%s/report-configuration.xml" % c.get('server', 'metadata')
    statpath = "%s/statistics.xml" % c.get('server', 'metadata')
    try:
        opts, args = getopt(argv[1:], "hc:s:", ["help", "config=", "stats="])
    except GetoptError, mesg:
        # print help information and exit:
        print "%s\nUsage:\nStatReports.py [-h] [-c <configuration-file>] [-s <statistics-file>]" % (mesg) 
        exit(2)
    for o, a in opts:
        if o in ("-h", "--help"):
            print "Usage:\nStatReports.py [-h] [-c <configuration-file>] [-s <statistics-file>]"
            exit()
        if o in ("-c", "--config"):
            configpath = a
        if o in ("-s", "--stats"):
            statpath = a


    try:
        statsdata = XML(open(statpath).read())
    except (IOError, ExpatError):
        print("StatReports: Failed to parse %s"%(statpath))
        exit(1)

    '''Reads report configuration info'''
    try:
        configdata = XML(open(configpath).read())
    except (IOError, ExpatError):
        print("StatReports: Failed to parse %s"%(configpath))
        exit(1)

    for reprt in configdata.findall('Report'):
        for deliv in reprt.findall('Delivery'):
            delivtype = deliv.get('type', default='nodes-digest')
            deliverymechanism = deliv.get('mechanism', default='invalid')

            reportsects = generatereport(reprt, deliv, delivtype, statsdata)
            
            if deliverymechanism == 'mail':
                mail(reportsects, deliv)
            elif deliverymechanism == 'rss':
                rss(reportsects, deliv, reprt)
            elif deliverymechanism == 'www':
                www(reportsects, deliv)
            else:
                print("StatReports: Invalid delivery mechanism in report-configuration!")
            deliverymechanism = ''
            delivtype = ''
