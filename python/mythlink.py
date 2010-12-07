#!/usr/bin/env python
#
# Creates symlinks to mythtv recordings using more-human-readable filenames.
# See --help for instructions.
#
# Automatically detects database settings from config.xml, and loads
# the mythtv recording directory from the database.

from MythTV import MythDB, findfile, Job
from optparse import OptionParser
import os

#def rename_all():
#    for rec in Recorded.getAllEntries():
#        

def link_all():
    # removing old content
    for path,dirs,files in os.walk(opts.dest, topdown=False):
        for fname in files:
            tmppath = os.path.join(path, fname)
            if not os.path.islink(tmppath):
                raise Exception('Non-link file found in destination path.')
            os.unlink(tmppath)
        os.rmdir(path)

    db = MythDB()
    if opts.live:
        recs = db.searchRecorded(livetv=True)
    else:
        recs = db.searchRecorded()
    for rec in recs:
        gen_link(rec)

def gen_link(rec):
    sg = findfile(rec.basename, rec.storagegroup, rec._db)
    source = os.path.join(sg.dirname, rec.basename)
    dest = os.path.join(opts.dest, rec.formatPath(format))
    if opts.underscores:
        dest = dest.replace(' ','_')
    sdest = dest.split('/')
    for i in range(2,len(sdest)):
        tmppath = os.path.join(*sdest[:i])
        if not os.access(tmppath, os.F_OK):
            os.mkdir(tmppath)
    os.symlink(source, dest)


parser = OptionParser(usage="usage: %prog [options] [jobid]")

parser.add_option("--dest", action="store", type="str", dest="dest",
        help="""Specify the directory for the links.  If no pathname is given, links
                will be created in the show_names directory inside of the current 
                MythTV data directory on this machine.

                WARNING: ALL symlinks within the destination directory and its
                subdirectories (recursive) will be removed.""")
parser.add_option("--jobid", action="store", type="int", dest="jobid",
        help="""Create a link only for the specified recording file.  This argument
                may be used with an automated user-job run on completion of a recording.""")
parser.add_option("--chanid", action="store", type="int", dest="chanid",
        help="""Create a link only for the specified recording file.  This argument
                must be used in combination with --starttime.  This argument may be used
                in a custom user-job, or through the event-driven notification system's
                "Recording Started" event.""")
parser.add_option("--starttime", action="store", type="int", dest="starttime",
        help="""Create a link only for the specified recording file.  This argument
                must be used in combination with --chanid.  This argument may be used
                in a custom user-job, or through the event-driven notification system's
                "Recording Started" event.""")
parser.add_option("--filename", action="store", type="str", dest="filename",
        help="""Create a link only for the specified recording file.  This argument may
                be used in a custom user-job, or through the event-driven notification
                system's "Recording Started" event.""")
parser.add_option("--live", action="store_true", default=False, dest="live",
        help="""Specify that LiveTV recordings are to be linked as well.  Default is to
                only process links for scheduled recordings.""")
parser.add_option("--format", action="store", dest="format",
        help="""Specify the output format to be used to generate link paths.""")
parser.add_option("--underscores", action="store", dest="underscores",
        help="""Replace whitespace in filenames with underscore characters.""")
parser.add_option('-v', '--verbose', action='store', type='string', dest='verbose',
        help='Verbosity level')

opts, args = parser.parse_args()

if opts.dest is None:
    opts.dest = '/mnt/mythtv/by-title'
if opts.format is None:
    format = '%T/(%oY%-%om%-%od) %S'
if opts.jobid:
    db = MythDB()
    job = Job(opts.jobid, db=db)
    rec = Recorded((job.chanid, job.starttime), db=db)
    gen_link(rec)
elif opts.chanid and opts.starttime:
    rec = Recorded((opts.chanid, opts.starttime)
    gen_link(rec)
elif opts.filename:
    db = MythDB()
    rec = db.searchRecorded(basename=opts.filename)
    gen_link(rec)
else:
    link_all()

