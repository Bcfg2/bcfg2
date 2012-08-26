#!/usr/bin/env python
#===============================================================================
#
#         FILE: accounts2xml.py
#
#        USAGE: ./accounts2xml.py filename node_name
#
#  DESCRIPTION: A python script to generate accounts.xml containing only the login
#               users from the given /etc/passwd file
#
#      OPTIONS: ---
# REQUIREMENTS: ---
#         BUGS: ---
#        NOTES: ---
#       AUTHOR: DongInn Kim (), dikim@cs.indiana.edu
# ORGANIZATION: Center for Research in Extreme Scale Technologies
#      VERSION: 1.0
#      CREATED: 05/13/2012 01:44:43 PM
#     REVISION: ---
#===============================================================================

# encoding: utf-8

"""
accounts2xml.py

This script coverts a csv file to an XML.
The script takes 1 paramenters
* filename

e.g., ./accounts2xml.py /etc/passwd

Created by Giovanni Collazo on 2011-02-19.
Copyright (c) 2011 24veces.com. All rights reserved.

Modified by DongInn Kim on 2012-05-13
Copyright (c) 2012 Indiana University. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

import sys
import csv
import os
import re
import grp
from xml.dom.minidom import Document

def main(args):
  
  try:
    filename = "./copied_passwd"
    with file(args[1], 'r') as original: data = original.read()
    with file(filename, 'w') as modified: modified.write("name:pass:uid:gid:gecos:home:shell\n" + data); modified.close()
    safe_filename = "Properties"
  except IndexError:
    print("ERROR: Please provide a filename.csv as the first argument")
    sys.exit()
    
  node_user = "UnixUser"
  node_group = "UnixGroup"

  f = csv.reader(open(filename, 'rb'), delimiter=':')
  
  doc = Document()
  root_element = doc.createElement(safe_filename)
  doc.appendChild(root_element)
  
  columns = f.next()
  
  groups = dict()
  for row in f:
    match = re.search(r'/bin/\w*sh', row[6])  # adjust this line to match the right shell path
    if match:
        item = doc.createElement(node_user)
        root_element.appendChild(item)
        extra_groups = os.popen("groups %s" % row[0]).readline()[:-1] 
        p_group = os.popen("id -gn %s" % row[0]).readline()[:-1]
        extra_groups_str = extra_groups.split(' : ')[1]
        populate_groups(groups, extra_groups_str)
        item.setAttribute('extra_groups', get_extra_group_str(extra_groups_str, p_group))
        create_col_nodes(columns, item, doc, row)
    
  for gkey, gval in groups.items():
    item = doc.createElement(node_group)
    root_element.appendChild(item)
    item.setAttribute('name', gkey)
    (gid,extra) = gval.split(':')
    item.setAttribute('gid', gid)

  output_file = "accounts.xml"
  doc.writexml(open(output_file, 'w'), addindent='    ', newl='\n') # Write file
  
  print("Done: Created %s" % output_file)
  os.remove(filename)

def get_extra_group_str(group_str, p_group):
    groups = group_str.split(' ')
    groups = [x for x in groups  if p_group != x]
    return ' '.join(groups)

  
def create_col_nodes(cols, item, doc, row): 
  for col in cols:
    if col == "gid":
        att = doc.createAttribute("group")
        att.nodeValue = grp.getgrgid(int(row.pop(0)))[0]
    else:
        att = doc.createAttribute(str.replace(col, " ", "_").lower())
        att.nodeValue = row.pop(0)

    if col != "pass":
        item.setAttributeNode(att)

def populate_groups(group_dic, group_str):
    for g in group_str.split(' '):
        if not group_dic.has_key(g):
            group_ent = os.popen("getent group %s" % g).readline()[:-1].split(':')
            gid = group_ent[2]
            extra = group_ent[3]
            extra_list = list(extra)
            for e in extra_list:
                if e == ',':
                    loc = extra_list.index(e)
                    extra_list[loc] = ' '
            extra = "".join(extra_list)
            group_dic[g] = gid + ":" + extra


if __name__ == "__main__":
  sys.exit(main(sys.argv))

# vim:set sr et ts=4 sw=4 ft=python fenc=utf-8: // See Vim, :help 'modeline'
# Created: Sun, 13 May 2012 13:44:43 -0400


