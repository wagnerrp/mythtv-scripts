#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#----------------------

import os
import sys
from ConfigParser import SafeConfigParser
from urllib import urlopen
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
# if ttvdb.py, optionally add config file
if 'ttvdb.py' in TVgrab.path:
    path = os.path.expanduser('~/.mythtv/ttvdb.conf')
    if os.access(path, os.F_OK):
        # apply title overrides
        cfg = SafeConfigParser()
        cfg.read(path)
        if 'series_name_override' in cfg.sections():
            ovr = [(title, cfg.get('series_name_override',title)) \
                    for title in cfg.options('series_name_override')]
            TVgrab.setOverride(ovr)
            TVgrab.append(' -c '+path)

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
    print len(todel)+' found'
    for vid in todel:
        print '      '+format_name(vid)
        vid.delete()

# loop through content to add
if len(toadd) > 0:
    print '--- Adding New Videos ---'
    print len(toadd)+' found'
    for vid in toadd:
        print '      '+format_name(vid),

        if vid.subtitle:
            matches = TVgrab.searchTitle(vid.title)
        else:
            matches = Mgrab.searchTitle(vid.title)

        if len(matches) == 0:
            print '... no matches, skipped.'
            continue
        elif len(matches) > 1:
            print '... multiple matches, skipped.'
            continue

        vid.inetref = matches[0][0]
        if vid.subtitle:
            data, cast, genre, country = \
                    TVgrab.getData(vid.inetref, vid.season, vid.episode)
        else:
            data, cast, genre, country = Mgrab.getData(vid.inetref)

        vid.data.update(data)

        for type in ('coverfile', 'screenshot', 'banner', 'fanart'):
            if vid[type] in ('No Cover','',None):
                # no images given
                continue

            if type == 'coverfile': name = 'coverart'
            else: name = type

            url = self.vid[type]
            if ',' in url:
                url = url.split(',',1)[0]

            if vid.season:
                if type == 'screenshot':
                    vid[type] = '%s Season %dx%d_%s.%s' % \
                            (vid.title, vid.season, vid.episode,
                             name, url.rsplit('.',1)[1])
                else:
                    vid[type] = '%s Season %d_%s.%s' % \
                            (vid.title, vid.season, name, url.rsplit('.',1)[1])
            else:
                vid[type] = '%s_%s.%s' % \
                            (vid.title, name, url.rsplit('.',1)[1])

            try:
                dstfp = vid._open(type, 'w', True)
                srcfp = urlopen(url)
                dstfp.write(srcfp.read())
                srcfp.close()
                dstfp.close()
            except:
                pass

        vid.create()
        for i in cast:
            vid.cast.add(i)
        for i in genre:
            vid.genre.add(i)
        for i in country:
            vid.country.add(i)
        print '... successful.'

