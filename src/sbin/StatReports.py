#!/usr/bin/env python

#Jun 7 2005
#StatReports

from ConfigParser import ConfigParser
from elementtree.ElementTree import *
from xml.parsers.expat import ExpatError
from xml.sax.saxutils import escape
from smtplib import SMTP
from time import asctime, strftime, strptime, ctime, gmtime
import re,string,os


def generateReport(report,delivery,deliverytype,statdata):
    reportSections = []


    current_date = asctime()[:10]
    baddata = ''
    modified = ''
    msg = ''
    mheader = ''
    dirty = ''
    clean = ''
    for machine in report.findall('Machine'):
        for node in statdata.findall('Node'):
	    if node.attrib['name'] == machine.attrib['name']:
	        if deliverytype == 'nodes-digest':
		    mheader="Machine: %s\n"%machine.attrib['name']
		for stats in node.findall('Statistics'):
		    if stats.attrib['state'] == 'clean' and current_date in stats.attrib['time']:
		        clean += "%s\n"%machine.attrib['name']
		    if report.attrib['modified'] == 'Y':#replace this with get
		        for modxml in stats.findall('Modified'):
			    if current_date in stats.attrib['time']:
			        modified+="\n%s\n"%tostring(modxml)
		    for bad in stats.findall('Bad'):
		        srtd = bad.findall('*')
		        srtd.sort(lambda x,y:cmp(tostring(x),tostring(y)))
		        strongbad = Element("Bad")
		        map(lambda x:strongbad.append(x),srtd)
		        baddata+="Time Ran:%s\n%s\n"%(stats.attrib['time'],tostring(strongbad))
		        dirty+="%s\n"%machine.attrib['name']
		        strongbad = ''

	if delivery.attrib['type'] == 'nodes-individual':#replace this with get
            if baddata != '':
                reportSections.append(("%s: Bcfg Nightly Errors"%machine.attrib['name'],"%s%s"%(modified,baddata)))
            else:
                if report.attrib['good'] == 'Y':
                    reportSections.append(("%s: Bcfg Nightly Good"%machine.attrib['name'],"%s%s"%(modified,baddata)))
	    baddata=''
	    modified=''
	else:
	    if not (modified == '' and baddata == ''):
	        msg += "%s %s %s\n"%(mheader,modified,baddata)
	    baddata=''
	    modified=''

    if delivery.attrib['type'] == 'nodes-digest':
        for destination in delivery.findall('Destination'):
       	    toaddr=destination.attrib['address']
	    if msg != '':
                reportSections.append(("Bcfg Nightly Errors","DIRTY:\n%s\nCLEAN:\n%s\nDETAILS:\n%s"%(dirty,clean,msg)))
	    else:
                if user.attrib['good'] == 'Y':
                    reportSections.append(("Bcfg Nightly All Machines Good","All Machines Nomnial"))




    if delivery.attrib['type'] == 'overview-stats':
	children = statdata.findall("Node")
	regex = string.join(map(lambda x:x.get("name"), report.findall('Machine')),'|')
	p = re.compile(regex)
	childstates = []
	for child in children:
	    if p.match(child.get("name")):
	        child.states = []
		for state in child.findall("Statistics"):
		    child.states.append((child.get("name"),state.get("state"),state.get("time")))
		if child.states != []:
		    childstates.append(child.states[len(child.states)-1])
		    childstates.sort(lambda x,y:cmp(x[0],y[0]))

	staleones=[]
        cleanones=[]
        dirtyones=[]
        unpingableones=[]

	for instance in childstates:
	    if instance[1]=="dirty":
	        dirtyones.append(instance)
	    elif instance[1]=="clean":
	        cleanones.append(instance)
	    if strptime(instance[2])[0]!=strptime(ctime())[0] \
	    or strptime(instance[2])[1]!=strptime(ctime())[1] \
	    or strptime(instance[2])[2]!=strptime(ctime())[2]:
	        staleones.append(instance)

	if staleones != []:
	    print "Pinging hosts that didn't run today. Please wait"
	for instance in staleones:
	    if os.system( 'ping -c 1 '+instance[0]+'.mcs.anl.gov &>/dev/null'):
	        staleones.remove(instance)
	        unpingableones.append(instance)

        statmsg=''
	statmsg+="SUMMARY INFORMATION:\n"
	statmsg+="Up & Not Running Nightly:     %d\n"%len(staleones)
	statmsg+="Unpingable:                   %d\n"%len(unpingableones)
	statmsg+="Dirty:                        %d\n"%len(dirtyones)
	statmsg+="Clean:                        %d\n"%len(cleanones)
	statmsg+="---------------------------------\n"
	total=len(cleanones)+len(dirtyones)
	statmsg+="Total:                        %d\n\n\n"%len(childstates)

	statmsg+="\n UP AND NOT RUNNING NIGHTLY:\n"
	for one in staleones:
	    statmsg+=one[0]+".mcs.anl.gov\n"
	statmsg+="\nDIRTY:\n"
	for one in dirtyones:
	    statmsg+=one[0]+".mcs.anl.gov\n"
	statmsg+="\nCLEAN:\n"
	for one in cleanones:
	    statmsg+=one[0]+".mcs.anl.gov\n"
	statmsg+="\nUNPINGABLE:\n"
	for one in unpingableones:
	    statmsg+=one[0]+".mcs.anl.gov\n"

        reportSections.append(("Bcfg Nightly Errors","%s"%(statmsg)))

    return reportSections



    
def mail(reportsections,delivery,deliverytype):
    current_date = asctime()[:10]
    mailer = SMTP('localhost')
    fromaddr = "root@netzero.mcs.anl.gov"

    for destination in delivery.findall('Destination'):
        toaddr = destination.attrib['address']
        for section in reportsections:
            msg="To: %s\nFrom: %s\nSubject: %s\n\n\n%s"%(toaddr,fromaddr,section[0],section[1])
            mailer.sendmail(fromaddr,toaddr,msg)
    mailer.quit()



def rss(reportsections,delivery,deliverytype):
    #need Report, Delivery, ReportSections(list of tuples)
	
    #check and see if rss file xists
    for destination in delivery.findall('Destination'):
        try:
	    fil = open(destination.attrib['address'],'r')
	    olddoc = XML(fil.read())
	    #read array of 9 most recent items out
            items = olddoc.find("channel").findall("item")[0:9]#defines the number of recent articles to keep
            fil.close()
	    fil = open(destination.attrib['address'],'w')
        except (IOError,ExpatError):
	    fil = open(destination.attrib['address'],'w')
	    items = []

        rss = Element("rss")
        channel = SubElement(rss,"channel")
        rss.set("version","2.0")
        chantitle = SubElement(channel, "title")
        chantitle.text = report.attrib['name']
        chanlink = SubElement(channel, "link")
        chanlink.text = "http://www.mcs.anl.gov/"#this can later link to WWW report if one gets published with this one
        chandesc = SubElement(channel, "description")
        chandesc.text = "Information regarding the 10 most recent bcfg2 runs."

        for section in reportsections:
            item = SubElement(channel, "item")
            title = SubElement(item, "title")
            title.text = section[0]
            description = SubElement(item,"description")
            description.text = "<pre>"+escape(section[1])+"</pre>"
            date = SubElement(item,"pubDate")
            date.text = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
            item = None
        if items != []:
            for item in items:
                channel.append(item)

        tree = "<?xml version=\"1.0\"?>"+tostring(rss)
        fil.write(tree)
        fil.close()


def www(reportsections,delivery,deliverytype):
    #need Report, Delivery, ReportSections(list of tuples)
	
    #check and see if rss file xists
    for destination in delivery.findall('Destination'):
        fil = open(destination.attrib['address'],'w')
	
        html = Element("HTML")
        body = SubElement(html,"BODY")
        for section in reportsections:
            SubElement(body,"br")
            item = SubElement(body, "div")
            title = SubElement(item,"h1")
            title.text = section[0]
            pre = SubElement(item,"pre")
            pre.text = section[1]
            SubElement(body,"hr")
            SubElement(body,"br")

        fil.write(tostring(html))
        fil.close()



if __name__ == '__main__':
    c = ConfigParser()
    c.read(['/etc/bcfg2.conf'])
    statpath = "%s/statistics.xml" % c.get('server', 'metadata')#this needs
    #to be configurable-- like options like, in case you want to read in a different file

    #configpath = "%s/machine-owners.xml" % c.get('server', 'metadata')
    configpath = "/sandbox/hagedorn/report-configuration.xml"
    '''Reads current state regarding statistics'''
    try:
        statdata = XML(open(statpath).read())
    except (IOError, ExpatError):
        print("StatReports: Failed to parse %s"%(statpath))

    '''Reads report configuration info'''
    try:
        configdata = XML(open(configpath).read())
    except (IOError, ExpatError):
        print("StatReports: Failed to parse  %s"%(configpath))


    for report in configdata.findall('Report'):
        for delivery in report.findall('Delivery'):
            deliverytype = delivery.get('type',default='nodes-digest')
            deliverymechanism = delivery.get('mechanism',default='invalid')

            reportsections = generateReport(report,delivery,deliverytype,statdata)
            
            if deliverymechanism == 'mail':
                mail(reportsections,delivery,deliverytype)
            elif deliverymechanism == 'rss':
                rss(reportsections,delivery,deliverytype)
            elif deliverymechanism == 'www':
                www(reportsections,delivery,deliverytype)
            else:
                print("StatReports: Invalid delivery mechanism in report-configuration!")
            deliverymechanism = ''
            deliverytype = ''
