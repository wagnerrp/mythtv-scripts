#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#----------------------

import os
import sys
try:
    from MythTV import MythVideo, VideoGrabber, MythLog
except:
    print 'ERROR: The python bindings are not installed'
    sys.exit(-1)

LOG = MythLog('MythVideo Scanner', lstr='general')
mvid = MythVideo()

def format_name(vid):
    # returns a string in the format 'TITLE[ - SEASONxEPISODE][ - SUBTITLE]'
    s = vid.title
    if vid.season:
        s += ' - %dx%02d' % (vid.season, vid.episode)
    if vid.subtitle:
        s += ' - '+vid.subtitle
    return s

# Load TV Grabber
try:
    TVgrab = VideoGrabber('TV', db=mvid)
except:
    print 'ERROR: Cannot find MythVideo TV grabber'
    sys.exit(-1)

# Load Movie Grabber
try:
    Mgrab = VideoGrabber('Movie', db=mvid)
except:
    print 'ERROR: Cannot find MythVideo Movie grabber'
    sys.exit(-1)

# pull new/old content list
LOG(LOG.GENERAL, 'Performing scan...')
toadd, todel = mvid.scanStorageGroups(False)

# print list of content to be deleted
if len(todel) > 0:
    print '--- Deleting Old Videos ---'
    print len(todel),' found'
    for vid in todel:
        print '      '+format_name(vid)
        vid.delete()

# loop through content to add
if len(toadd) > 0:
    print '--- Adding New Videos ---'
    print len(toadd),' found'
    for vid in toadd:
        print '      '+format_name(vid),

        if vid.subtitle:
            matches = TVgrab.sortedSearch(vid.title, vid.subtitle)
        else:
            matches = Mgrab.sortedSearch(vid.title)

        if len(matches) == 0:
            print '... no matches, skipped.'
            continue
        elif len(matches) > 1:
            if matches[0].levenshtein > 0:
                print '... multiple matches, skipped.'
                continue

        vid.create()
        vid.importMetadata(matches[0])
        print '... successful.'

