#!/usr/bin/env python

from MythTV import MythDB, MythBE, Recorded
from socket import timeout

import os
import sys

def human_size(s):
    s = float(s)
    o = 0
    while s > 1000:
        s /= 1000
        o += 1
    return str(round(s,1))+('B ','KB','MB','GB')[o]

class File( str ):
    #Utility class to allow deletion and terminal printing of files.
    def __new__(self, host, group, path, name, size):
        return str.__new__(self, name)
    def __init__(self, host, group, path, name, size):
        self.host = host
        self.group = group
        self.path = path
        self.size = int(size)
    def pprint(self):
        name = '%s: %s' % (self.host, os.path.join(self.path, self))
        print u'  {0:<90}{1:>8}'.format(name, human_size(self.size))
    def delete(self):
        be = MythBE(self.host, db=DB)
        be.deleteFile(self, self.group)

class MyRecorded( Recorded ):
    #Utility class to allow deletion and terminal printing of orphaned recording entries.
    _table = 'recorded'
    def pprint(self):
        name = u'{0.hostname}: {0.title}'.format(self)
        if self.subtitle:
            name += ' - '+self.subtitle
        print u'  {0:<70}{1:>28}'.format(name,self.basename)

def printrecs(title, recs):
    # print out all recordings in list, followed by a count
    print title
    for rec in sorted(recs, key=lambda x: x.title):
        rec.pprint()
    print u'{0:>88}{1:>12}'.format('Count:',len(recs))

def printfiles(title, files):
    # print out all files in list, followed by a total size
    print title
    for f in sorted(files, key=lambda x: x.path):
        f.pprint()
    size = sum([f.size for f in files])
    print u'{0:>88}{1:>12}'.format('Total:',human_size(size))

def populate(host=None):
    # scan through all accessible backends to generate a new list of orphaned content
    unfiltered = []
    kwargs = {'livetv':True}
    if host:
        # if the host was defined on the command line, check to make sure such a
        # host is defined in the database
        with DB as c:
            c.execute("""SELECT count(1) FROM settings
                         WHERE hostname=%s AND value=%s""",
                        (host, 'BackendServerIP'))
            if c.fetchone()[0] == 0:
                raise Exception('Invalid hostname specified on command line.')
        hosts = [host]
        kwargs['hostname'] = host
    else:
        # else, pull a list of all defined backends from the database
        with DB as c:
            c.execute("""SELECT hostname FROM settings
                         WHERE value='BackendServerIP'""")
            hosts = [r[0] for r in c.fetchall()]
    for host in hosts:
        for sg in DB.getStorageGroup():
            # skip special storage groups intended for MythVideo
            # this list will need to be added to as additional plugins
            # start using their own storage groups
            if sg.groupname in ('Videos','Banners','Coverart',\
                                'Fanart','Screenshots','Trailers'):
                continue
            try:
                dirs,files,sizes = BE.getSGList(host, sg.groupname, sg.dirname)
                for f,s in zip(files,sizes):
                    newfile = File(host, sg.groupname, sg.dirname, f, s)
                    # each filename should be unique among all storage directories
                    # defined on all backends
                    # store one copy of a file, ignoring where the file actually exists
                    if newfile not in unfiltered:
                        unfiltered.append(newfile)
            except:
                pass

    recs = list(DB.searchRecorded(**kwargs))

    zerorecs = []
    orphvids = []
    for rec in list(recs):
        # run through list of recordings, matching recording basenames with
        # found files, and removing from both lists
        if rec.basename in unfiltered:
            recs.remove(rec)
            i = unfiltered.index(rec.basename)
            f = unfiltered.pop(i)
            if f.size < 1024:
                zerorecs.append(rec)
            # remove any file with the same basename, these could be snapshots, failed
            # transcode temporary files, or anything else relating to a non-orphaned
            # recording
            name = rec.basename.rsplit('.',1)[0]
            for f in list(unfiltered):
                if name in f:
                    unfiltered.remove(f)

    # filter remaining files for those with recording extensions
    for f in list(unfiltered):
        if not (f.endswith('.mpg') or f.endswith('.nuv')):
            continue
        orphvids.append(f)
        unfiltered.remove(f)

    # filter remaining files for those with image extensions
    orphimgs = []
    for f in list(unfiltered):
        if not f.endswith('.png'):
            continue
        orphimgs.append(f)
        unfiltered.remove(f)

    # filter remaining files for those that look like database backups
    dbbackup = []
    for f in list(unfiltered):
        if 'sql' not in f:
            continue
        dbbackup.append(f)
        unfiltered.remove(f)

    return (recs, zerorecs, orphvids, orphimgs, dbbackup, unfiltered)

def delete_recs(recs):
    printrecs('The following recordings will be deleted', recs)
    print 'Are you sure you want to continue?'
    try:
        res = raw_input('> ')
        while True:
            if res == 'yes':
                for rec in recs:
                    rec.delete(True, True)
                break
            elif res == 'no':
                break
            else:
                res = raw_input("'yes' or 'no' > ")
    except MythError:
        name = u'{0.hostname}: {0.title}'.format(self)
        if self.subtitle:
            name += ' - '+self.subtitle
        print "Warning: Failed to delete '" + name + "'"
    except KeyboardInterrupt:
        pass
    except EOFError:
        sys.exit(0)

def delete_files(files):
    printfiles('The following files will be deleted', files)
    print 'Are you sure you want to continue?'
    try:
        res = raw_input('> ')
        while True:
            if res == 'yes':
                for f in files:
                    f.delete()
                break
            elif res == 'no':
                break
            else:
                res = raw_input("'yes' or 'no' > ")
    except KeyboardInterrupt:
        pass
    except EOFError:
        sys.exit(0)

def main(host=None):
   while True:
        recs, zerorecs, orphvids, orphimgs, dbbackup, unfiltered = populate(host)

        if len(recs):
            printrecs("Recordings with missing files", recs)
        if len(zerorecs):
            printrecs("Zero byte recordings", zerorecs)
        if len(orphvids):
            printfiles("Orphaned video files", orphvids)
        if len(orphimgs):
            printfiles("Orphaned snapshots", orphimgs)
        if len(dbbackup):
            printfiles("Database backups", dbbackup)
        if len(unfiltered):
            printfiles("Other files", unfiltered)

        opts = []
        if len(recs):
            opts.append(['Delete orphaned recording entries', delete_recs, recs])
        if len(zerorecs):
            opts.append(['Delete zero byte recordings', delete_recs, zerorecs])
        if len(orphvids):
            opts.append(['Delete orphaned video files', delete_files, orphvids])
        if len(orphimgs):
            opts.append(['Delete orphaned snapshots', delete_files, orphimgs])
        if len(unfiltered):
            opts.append(['Delete other files', delete_files, unfiltered])
        opts.append(['Refresh list', None, None])
        print 'Please select from the following'
        for i, opt in enumerate(opts):
            print u' {0}. {1}'.format(i+1, opt[0])

        try:
            inner = True
            res = raw_input('> ')
            while inner:
                try:
                    res = int(res)
                except:
                    res = raw_input('input number. ctrl-c to exit > ')
                    continue
                if (res <= 0) or (res > len(opts)):
                    res = raw_input('input number within range > ')
                    continue
                break
            opt = opts[res-1]
            if opt[1] is None:
                continue
            else:
                opt[1](opt[2])

        except KeyboardInterrupt:
            break
        except EOFError:
            sys.exit(0)

DB = MythDB()
BE = MythBE(db=DB)
DB.searchRecorded.handler = MyRecorded

if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        main()

