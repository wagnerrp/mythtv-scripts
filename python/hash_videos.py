#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
# Name: hash_videos.py
# Python Script
# Author: Raymond Wagner
# Purpose
#   This script will regenerate the hash values associated with
#   videos in the MythVideo database.
#---------------------------

from MythTV import Video

def print_aligned(left, right):
    indent = 100 - len(left)
    print left, indent*' ', right

for vid in Video.getAllEntries():
    if vid.hash != 'NULL':
        print_aligned(vid.filename, 'skipped')
        continue
    vid.hash = vid.getHash()
    vid.update()
    print_aligned(vid.filename, vid.hash)
