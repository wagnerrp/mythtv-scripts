#!/usr/bin/env python

from MythTV import Job, Recorded, Grabber

from optparse import OptionParser
import sys
import os

################################
#### adjust these as needed ####
transcoder = 'cp'
flush_commskip = False
build_seektable = False
################################

def runjob(jobid=None, chanid=None, starttime=None):
    if jobid:
        job = Job(jobid)
        chanid = job.chanid
        starttime = job.starttime
    rec = Recorded((chanid, starttime))

    for sg in rec.db.getStorageGroup(groupname=rec.storagegroup):
        if os.access(os.path.join(sg.dirname, rec.basename), os.F_OK):
            break
    else:
        print 'Local access to recording not found.'
        sys.exit(1)

    infile = os.path.join(sg.dirname, rec.basename)
    outfile = '%s.mkv' % infile.rsplit('.',1)[0]

    task = Grabber(path=transcoder)
    try:
##############################################
#### probably need to adjust this one too ####
        task.command('"%s"' % infile,
                     '"%s"' % outfile)
##############################################
    except MythError, e:
        print 'Command failed with output:\n%s' % e.stderr
        sys.exit(e.returncode)

    rec.basename = outfile
    os.remove(infile)
    rec.filesize = os.path.getsize(outfile)
    rec.transcoded = 1
    c = rec.db.cursor()
    c.execute("""DELETE FROM recordedseek
                 WHERE chanid=%s AND starttime=%s""",
                         (chanid, starttime))
    c.close()

    if flush_commskip:
        c = rec.db.cursor()
        c.execute("""DELETE FROM recordedmarkup
                     WHERE chanid=%s AND starttime=%s""",
                         (chanid, starttime))
        c.close()
        rec.bookmark = 0
        rec.cutlist = 0

    if build_seektable:
        task = Grabber(path='mythcommflag')
        task.command('--chanid %s' % chanid,
                     '--starttime %s' % starttime,
                     '--rebuild')

    rec.update()


def main():
    parser = OptionParser(usage="usage: %prog [options] [jobid]")

    parser.add_option('--chanid', action='store', type='int', dest='chanid',
            help='Use chanid for manual operation')
    parser.add_option('--starttime', action='store', type='int', dest='starttime',
            help='Use starttime for manual operation')
    parser.add_option('-v', '--verbose', action='store', type='string', dest='verbose',
            help='Verbosity level')

    opts, args = parser.parse_args()

    if opts.verbose:
        if opts.verbose == 'help':
            print MythLog.helptext
            sys.exit(0)
        MythLog._setlevel(opts.verbose)

    if len(args) == 1:
        runjob(jobid=args[0])
    elif opts.chanid and opts.starttime:
        runjob(chanid=opts.chanid, starttime=opts.starttime)
    else:
        print 'Script must be provided jobid, or chanid and starttime.'
        sys.exit(1)

if __name__ == '__main__':
    main()

