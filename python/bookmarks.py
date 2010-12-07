#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#----------------------

import os
import sys
from HTMLParser import HTMLParser
try:
    from MythTV import MythDB
    from MythTV.database import DBDataWrite
except:
    print 'ERROR: The python bindings are not installed'
    sys.exit(-1)

class Bookmark( DBDataWrite ):
    _table = 'websites'
    _defaults = {'id':None, 'category':u'', 'name':u'', 'url':u''}
    _schema_value = 'BrowserDBSchemaVer'
    _schema_local = 1002
    _schema_name = 'MythBrowser'

    def create(self, data=None):
        id = DBDataWrite.create(self, data)
        self.wheredat = (id,)
        self._pull()
        return self

class Parser( HTMLParser ):
    def __init__(self):
        HTMLParser.__init__(self)
        self.stack = []
    def handle_starttag(self, tag, attrs):
        if tag == 'h3':
            # new category, push to stack
            self.stack.append('h3')
        elif not len(self.stack):
            # no categories, refuse links
            return
        elif tag == 'a':
            # new bookmark, push to stack
            d = dict(attrs)
            self.stack.append(d['href'])
            self.stack.append('a')
    def handle_endtag(self, tag):
        if not len(self.stack):
            # empty stack, do nothing
            return
        elif tag == 'dl':
            # drop out of category, pop from stack
            self.stack.pop()
    def handle_data(self, data):
        if not len(self.stack):
            # empty stack, do nothing
            return
        elif self.stack[-1] == 'h3':
            # new category name, swap on stack
            self.stack[-1] = data
        elif self.stack[-1] == 'a':
            # new link name, swap on stack
            self.stack[-1] = data
            # create new bookmark in database
            b = Bookmark(db=db)
            b.name = self.stack.pop()
            b.url = self.stack.pop()
            b.category = self.stack[-1]
            b.create()

# select file
bookmark_file = '~/bookmarks.html'
if len(sys.argv) == 2:
    bookmark_file = sys.argv[1]

# check if file exists
if not os.access(os.path.expanduser(bookmark_file), os.F_OK):
    print 'ERROR: bookmark file could not be found'
    sys.exit(-1)

# connect to database
try:
    db = MythDB()
except:
    print 'ERROR: database could not be accessed'
    sys.exit(-1)

# flush old entries and reset counter
c = db.cursor()
c.execute("""TRUNCATE TABLE websites""")
c.close()

# read in file
fp = open(os.path.expanduser(bookmark_file))
data = ''.join(fp.readlines())
fp.close()

# parse file for bookmarks
parser = Parser()
parser.feed(data)

