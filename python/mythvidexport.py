#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
# Name: mythvidexport.py
# Python Script
# Author: Raymond Wagner
# Purpose
#   This python script is intended to function as a user job, run through
#   mythjobqueue, capable of exporting recordings into MythVideo.
#---------------------------
__title__  = "MythVidExport"
__author__ = "Raymond Wagner"
__version__= "v0.7.2"

usage_txt = """
This script can be run from the command line, or called through the mythtv
jobqueue.  The input format will be:
  mythvidexport.py [options] <--chanid <channel id>> <--starttime <start time>>
                 --- or ---
  mythvidexport.py [options] %JOBID%

Options are:
        --mformat <format string>
        --tformat <format string>
        --gformat <format string>
            overrides the stored format string for a single run
        --listingonly
            use EPG data rather than grabbers for metadata
            will still try to grab episode and season information from ttvdb.py
        --seektable            copy seek data from recording
        --skiplist             copy commercial detection from recording
        --cutlist              copy manual commercial cutlist from recording

Additional functions are available beyond exporting video
  mythvidexport.py <options>
        -h, --help             show this help message
        -p, --printformat      print existing format strings
        -f, --helpformat       lengthy description for formatting strings
        --mformat <string>     replace existing Movie format
        --tformat <string>     replace existing TV format
        --gformat <string>     replace existing Generic format
"""

from MythTV import MythDB, Job, Recorded, Video, VideoGrabber,\
                   MythLog, MythError, static, MythBE
from optparse import OptionParser
from socket import gethostname

import os
import re
import sys
import time
import hashlib

def create_dummy_video(db=None):
    db = MythDB(db)

def hashfile(fd):
    hasher = hashlib.sha1()
    while True:
        buff = fd.read(2**16)
        if len(buff) == 0:
            break
        hasher.update(buff)
    return hasher.hexdigest()

class VIDEO:
    def __init__(self, opts, jobid=None):
        if jobid:
            self.job = Job(jobid)
            self.chanid = self.job.chanid
            self.starttime = self.job.starttime
            self.job.update(status=Job.STARTING)
        else:
            self.job = None
            self.chanid = opts.chanid
            self.starttime = opts.starttime

        self.opts = opts
        self.db = MythDB()
        self.log = MythLog(module='mythvidexport.py', db=self.db)

        # load setting strings
        self.get_format()

        # prep objects
        self.rec = Recorded((self.chanid,self.starttime), db=self.db)
        self.log(MythLog.GENERAL, MythLog.INFO, 'Using recording',
                        '%s - %s' % (self.rec.title, self.rec.subtitle))
        self.vid = Video(db=self.db).create({'title':'', 'filename':'', 'host':gethostname()})

        # process data
        self.get_meta()
        self.get_dest()

        # save file
        self.copy()
        if opts.seekdata:
            self.copy_seek()
        if opts.skiplist:
            self.copy_markup(static.MARKUP.MARK_COMM_START,
                             static.MARKUP.MARK_COMM_END)
        if opts.cutlist:
            self.copy_markup(static.MARKUP.MARK_CUT_START,
                             static.MARKUP.MARK_CUT_END)
        self.vid.update()

        # delete old file
        if opts.delete:
            self.rec.delete()

    def get_format(self):
        host = self.db.gethostname()
        # TV Format
        if self.opts.tformat:
            self.tfmt = self.opts.tformat
        elif self.db.settings[host]['mythvideo.TVexportfmt']:
            self.tfmt = self.db.settings[host]['mythvideo.TVexportfmt']
        else:
            self.tfmt = 'Television/%TITLE%/Season %SEASON%/'+\
                            '%TITLE% - S%SEASON%E%EPISODEPAD% - %SUBTITLE%'

        # Movie Format
        if self.opts.mformat:
            self.mfmt = self.opts.mformat
        elif self.db.settings[host]['mythvideo.MOVIEexportfmt']:
            self.mfmt = self.db.settings[host]['mythvideo.MOVIEexportfmt']
        else:
            self.mfmt = 'Movies/%TITLE%'

        # Generic Format
        if self.opts.gformat:
            self.gfmt = self.opts.gformat
        elif self.db.settings[host]['mythvideo.GENERICexportfmt']:
            self.gfmt = self.db.settings[host]['mythvideo.GENERICexportfmt']
        else:
            self.gfmt = 'Videos/%TITLE%'

    def get_meta(self):
        self.vid.hostname = self.db.gethostname()
        if self.rec.subtitle:  # subtitle exists, assume tv show
            self.type = 'TV'
            self.log(self.log.GENERAL, self.log.INFO, 'Attempting TV export.')
            grab = VideoGrabber(self.type)
            match = grab.sortedSearch(self.rec.title, self.rec.subtitle)
        else:                   # assume movie
            self.type = 'MOVIE'
            self.log(self.log.GENERAL, self.log.INFO, 'Attempting Movie export.')
            grab = VideoGrabber(self.type)
            match = grab.sortedSearch(self.rec.title)

        if len(match) == 0:
            # no match found
            self.log(self.log.GENERAL, self.log.INFO, 'Falling back to generic export.')
            self.get_generic()
        elif (len(match) > 1) & (match[0].levenshtein > 0):
            # multiple matches found, and closest is not exact
            self.vid.delete()
            raise MythError('Multiple metadata matches found: '\
                                                   +self.rec.title)
        else:
            self.log(self.log.GENERAL, self.log.INFO, 'Importing content from', match[0].inetref)
            self.vid.importMetadata(grab.grabInetref(match[0]))
            self.log(self.log.GENERAL, self.log.INFO, 'Import complete')

    def get_generic(self):
        self.vid.title = self.rec.title
        if self.rec.subtitle:
            self.vid.subtitle = self.rec.subtitle
        if self.rec.description:
            self.vid.plot = self.rec.description
        if self.rec.originalairdate:
            self.vid.year = self.rec.originalairdate.year
            self.vid.releasedate = self.rec.originalairdate
        lsec = (self.rec.endtime-self.rec.starttime).seconds
        self.vid.length = str(lsec/60)
        for member in self.rec.cast:
            if member.role == 'director':
                self.vid.director = member.name
            elif member.role == 'actor':
                self.vid.cast.append(member.name)
        self.type = 'GENERIC'

    def get_dest(self):
        if self.type == 'TV':
            self.vid.filename = self.process_fmt(self.tfmt)
        elif self.type == 'MOVIE':
            self.vid.filename = self.process_fmt(self.mfmt)
        elif self.type == 'GENERIC':
            self.vid.filename = self.process_fmt(self.gfmt)

    def process_fmt(self, fmt):
        # replace fields from viddata
        #print self.vid.data
        ext = '.'+self.rec.basename.rsplit('.',1)[1]
        rep = ( ('%TITLE%','title','%s'),   ('%SUBTITLE%','subtitle','%s'),
            ('%SEASON%','season','%d'),     ('%SEASONPAD%','season','%02d'),
            ('%EPISODE%','episode','%d'),   ('%EPISODEPAD%','episode','%02d'),
            ('%YEAR%','year','%s'),         ('%DIRECTOR%','director','%s'))
        for tag, data, format in rep:
            if self.vid[data]:
                fmt = fmt.replace(tag,format % self.vid[data])
            else:
                fmt = fmt.replace(tag,'')

        # replace fields from program data
        rep = ( ('%HOSTNAME','hostname','%s'),('%STORAGEGROUP%','storagegroup','%s'))
        for tag, data, format in rep:
            data = getattr(self.rec, data)
            fmt = fmt.replace(tag,format % data)

#       fmt = fmt.replace('%CARDID%',self.rec.cardid)
#       fmt = fmt.replace('%CARDNAME%',self.rec.cardid)
#       fmt = fmt.replace('%SOURCEID%',self.rec.cardid)
#       fmt = fmt.replace('%SOURCENAME%',self.rec.cardid)
#       fmt = fmt.replace('%CHANNUM%',self.rec.channum)
#       fmt = fmt.replace('%CHANNAME%',self.rec.cardid)

        if len(self.vid.genre):
            fmt = fmt.replace('%GENRE%',self.vid.genre[0].genre)
        else:
            fmt = fmt.replace('%GENRE%','')
#       if len(self.country):
#           fmt = fmt.replace('%COUNTRY%',self.country[0])
#       else:
#           fmt = fmt.replace('%COUNTRY%','')
        return fmt+ext

    def copy(self):
        stime = time.time()
        srcsize = self.rec.filesize
        htime = [stime,stime,stime,stime]

        self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Copying myth://%s@%s/%s"\
               % (self.rec.storagegroup, self.rec.hostname, self.rec.basename)\
                                                    +" to myth://Videos@%s/%s"\
                                          % (self.vid.host, self.vid.filename))
        srcfp = self.rec.open('r')
        dstfp = self.vid.open('w')

        if self.job:
            self.job.setStatus(Job.RUNNING)
        tsize = 2**24
        while tsize == 2**24:
            tsize = min(tsize, srcsize - dstfp.tell())
            dstfp.write(srcfp.read(tsize))
            htime.append(time.time())
            rate = float(tsize*4)/(time.time()-htime.pop(0))
            remt = (srcsize-dstfp.tell())/rate
            if self.job:
                self.job.setComment("%02d%% complete - %d seconds remaining" %\
                            (dstfp.tell()*100/srcsize, remt))
        srcfp.close()
        dstfp.close()

        self.vid.hash = self.vid.getHash()

        self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Transfer Complete",
                            "%d seconds elapsed" % int(time.time()-stime))

        if self.opts.reallysafe:
            if self.job:
                self.job.setComment("Checking file hashes")
            self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Checking file hashes.")
            srchash = hashfile(self.rec.open('r'))
            dsthash = hashfile(self.rec.open('r'))
            if srchash != dsthash:
                raise MythError('Source hash (%s) does not match destination hash (%s)' \
                            % (srchash, dsthash))
        elif self.opts.safe:
            self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Checking file sizes.")
            be = MythBE(db=self.vid._db)
            try:
                srcsize = be.getSGFile(self.rec.hostname, self.rec.storagegroup, \
                                       self.rec.basename)[1]
                dstsize = be.getSGFile(self.vid.host, 'Videos', self.vid.filename)[1]
            except:
                raise MythError('Could not query file size from backend')
            if srcsize != dstsize:
                raise MythError('Source size (%d) does not match destination size (%d)' \
                            % (srcsize, dstsize))

        if self.job:
            self.job.setComment("Complete - %d seconds elapsed" % \
                            (int(time.time()-stime)))
            self.job.setStatus(Job.FINISHED)

    def copy_seek(self):
        for seek in self.rec.seek:
            self.vid.markup.add(seek.mark, seek.offset, seek.type)

    def copy_markup(self, start, stop):
        for mark in self.rec.markup:
            if mark.type in (start, stop):
                self.vid.markup.add(mark.mark, 0, mark.type)

def usage_format():
    usagestr = """The default strings are:
    Television: Television/%TITLE%/Season %SEASON%/%TITLE% - S%SEASON%E%EPISODEPAD% - %SUBTITLE%
    Movie:      Movies/%TITLE%
    Generic:    Videos/%TITLE%

Available strings:
    %TITLE%:         series title
    %SUBTITLE%:      episode title
    %SEASON%:        season number
    %SEASONPAD%:     season number, padded to 2 digits
    %EPISODE%:       episode number
    %EPISODEPAD%:    episode number, padded to 2 digits
    %YEAR%:          year
    %DIRECTOR%:      director
    %HOSTNAME%:      backend used to record show
    %STORAGEGROUP%:  storage group containing recorded show
    %GENRE%:         first genre listed for recording
"""
#    %CARDID%:        ID of tuner card used to record show
#    %CARDNAME%:      name of tuner card used to record show
#    %SOURCEID%:      ID of video source used to record show
#    %SOURCENAME%:    name of video source used to record show
#    %CHANNUM%:       ID of channel used to record show
#    %CHANNAME%:      name of channel used to record show
#    %COUNTRY%:       first country listed for recording
    print usagestr

def print_format():
    db = MythDB()
    host = gethostname()
    tfmt = db.settings[host]['mythvideo.TVexportfmt']
    if not tfmt:
        tfmt = 'Television/%TITLE%/Season %SEASON%/%TITLE% - S%SEASON%E%EPISODEPAD% - %SUBTITLE%'
    mfmt = db.settings[host]['mythvideo.MOVIEexportfmt']
    if not mfmt:
        mfmt = 'Movies/%TITLE%'
    gfmt = db.settings[host]['mythvideo.GENERICexportfmt']
    if not gfmt:
        gfmt = 'Videos/%TITLE%'
    print "Current output formats:"
    print "    TV:      "+tfmt
    print "    Movies:  "+mfmt
    print "    Generic: "+gfmt

def main():
    parser = OptionParser(usage="usage: %prog [options] [jobid]")

    parser.add_option("-f", "--helpformat", action="store_true", default=False, dest="fmthelp",
            help="Print explination of file format string.")
    parser.add_option("-p", "--printformat", action="store_true", default=False, dest="fmtprint",
            help="Print current file format string.")
    parser.add_option("--tformat", action="store", type="string", dest="tformat",
            help="Use TV format for current task. If no task, store in database.")
    parser.add_option("--mformat", action="store", type="string", dest="mformat",
            help="Use Movie format for current task. If no task, store in database.")
    parser.add_option("--gformat", action="store", type="string", dest="gformat",
            help="Use Generic format for current task. If no task, store in database.")
    parser.add_option("--chanid", action="store", type="int", dest="chanid",
            help="Use chanid for manual operation")
    parser.add_option("--starttime", action="store", type="int", dest="starttime",
            help="Use starttime for manual operation")
    parser.add_option("--listingonly", action="store_true", default=False, dest="listingonly",
            help="Use data from listing provider, rather than grabber")
    parser.add_option("--seekdata", action="store_true", default=False, dest="seekdata",
            help="Copy seekdata from source recording.")
    parser.add_option("--skiplist", action="store_true", default=False, dest="skiplist",
            help="Copy commercial detection from source recording.")
    parser.add_option("--cutlist", action="store_true", default=False, dest="cutlist",
            help="Copy manual commercial cuts from source recording.")
    parser.add_option('--safe', action='store_true', default=False, dest='safe',
            help='Perform quick sanity check of exported file using file size.')
    parser.add_option('--really-safe', action='store_true', default=False, dest='reallysafe',
            help='Perform slow sanity check of exported file using SHA1 hash.')
    parser.add_option("--delete", action="store_true", default=False,
            help="Delete source recording after successful export. Enforces use of --safe.")

    MythLog.loadOptParse(parser)

    opts, args = parser.parse_args()

    if opts.verbose:
        if opts.verbose == 'help':
            print MythLog.helptext
            sys.exit(0)
        MythLog._setlevel(opts.verbose)

    if opts.fmthelp:
        usage_format()
        sys.exit(0)

    if opts.fmtprint:
        print_format()
        sys.exit(0)

    if opts.delete:
        opts.safe = True

    if opts.chanid and opts.starttime:
        export = VIDEO(opts)
    elif len(args) == 1:
        try:
            export = VIDEO(opts,int(args[0]))
        except Exception, e:
            Job(int(args[0])).update({'status':Job.ERRORED,
                                      'comment':'ERROR: '+e.args[0]})
            MythLog(module='mythvidexport.py').logTB(MythLog.GENERAL)
            sys.exit(1)
    else:
        if opts.tformat or opts.mformat or opts.gformat:
            db = MythDB()
            host = gethostname()
            if opts.tformat:
                print "Changing TV format to: "+opts.tformat
                db.settings[host]['mythvideo.TVexportfmt'] = opts.tformat
            if opts.mformat:
                print "Changing Movie format to: "+opts.mformat
                db.settings[host]['mythvideo.MOVIEexportfmt'] = opts.mformat
            if opts.gformat:
                print "Changing Generic format to: "+opts.gformat
                db.settings[hosts]['mythvideo.GENERICexportfmt'] = opts.gformat
            sys.exit(0)
        else:
            parser.print_help()
            sys.exit(2)

if __name__ == "__main__":
    main()

