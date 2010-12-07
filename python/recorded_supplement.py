#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
# Name: recorded_supplement.py
# Python Script
# Author: Raymond Wagner
# Purpose
#   This python script is intended to function as a user job, run through
#   mythjobqueue, and pull supplementary metadata for recordings, pulled
#   from the metadata grabbers defined in MythVideo.
#---------------------------

from MythTV import Recorded, Job, VideoGrabber, MythLog, MythError
from optparse import OptionParser

import sys

def import_metadata(rec):
    if rec.subtitle:
        grab = VideoGrabber('TV', db=rec._db)
        match = grab.sortedSearch(rec.title, rec.subtitle)
    else:
        grab = VideoGrabber('TV', db=rec._db)
        match = grab.sortedSearch(rec.title)

    if len(match) == 0:
        # no match
        raise MythError('No match found')
    elif len(match) > 1:
        # multiple found, only accept exact match
        if match[0].levenshtein > 0:
            raise MythError('No exact match found')

    # use allowed match
    rec.importMetadata(grab.grabInetref(match[0]))


def main():
    parser = OptionParser(usage="usage: %prog [options] [jobid]")

    parser.add_option("--chanid", action="store", type="int", dest="chanid",
            help="Use chanid for manual operation")
    parser.add_option("--starttime", action="store", type="int", dest="starttime",
            help="Use starttime for manual operation")
#    parser.add_option("-s", "--simulation", action="store_true", default=False, dest="sim",
#            help="Simulation (dry run), no files are copied or new entries made")
    parser.add_option('-v', '--verbose', action='store', type='string', dest='verbose',
            help='Verbosity level')

    opts, args = parser.parse_args()

    if opts.verbose:
        if opts.verbose == 'help':
            print MythLog.helptext
            sys.exit(0)
        MythLog._setlevel(opts.verbose)

    if opts.chanid and opts.starttime:
        job = None
        rec = Recorded((opts.chanid,opts.starttime))
    elif len(args) == 1:
        job = Job(int(args[0]))
        rec = Recorded((job.chanid,job.starttime), db=job._db)
    else:
        parser.print_help()
        sys.exit(2)

    try:
        import_metadata(rec)
    except Exception, e:
        if job is None:
            raise
        else:
            job.update({'status':job.ERRORED,
                        'comment':'ERROR: %s' % e.args[0]})
            sys.exit(1)


if __name__ == "__main__":
    main()

