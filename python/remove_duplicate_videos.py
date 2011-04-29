#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
# Name: remove_duplicate_videos.py
# Python Script
# Author: Raymond Wagner
# Purpose
#   For reasons unknown, some people continue to get duplicate file
#   entries in their MythVideo database. This script will detail those
#   duplicate files based off hash number, and optionally delete them.
#---------------------------
__title__  = "Remove Duplicate Videos"
__author__ = "Raymond Wagner"
__version__= "v0.5.0"

from optparse import OptionParser
from MythTV import Video

def format_name(vid):
    # returns a string in the format 'TITLE[ - SEASONxEPISODE][ - SUBTITLE]'
    s = vid.title
    if vid.season:
        s += ' - %dx%02d' % (vid.season, vid.episode)
    if vid.subtitle:
        s += ' - '+vid.subtitle
    return s

def FindDuplicates(dodelete):
    dupvids = []
    vids = sorted(Video.getAllEntries(), key=lambda v: v.hash)

    for i in range(len(vids)-1):
        if vids[i].hash == 'NULL':
            continue
        if vids[i].hash == vids[i+1].hash:
            dupvids.append(vids[i+1])

    if dodelete:
        for vid in dupvids:
            vid.delete()

    return dupvids

def main():
    parser = OptionParser(usage="usage: %prog [options] [jobid]")

    parser.add_option("-s", "--dry-run", action="store_true", default=False,
            dest="dryrun", help="Print out duplicates but do not delete.")

    opts, args = parser.parse_args()

    dups = FindDuplicates(not opts.dryrun)

    if len(dups):
        print len(dups), 'Duplicates Found!'
        print '----------------------'
        for vid in dups:
            print '  '+format_name(vid)
    else:
        print 'No Duplicates Found!'

if __name__ == "__main__":
    main()

