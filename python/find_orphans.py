#!/usr/bin/env python

from MythTV import MythDB, MythBE, MythLog, Recorded as _Recorded
from MythTV.utility import datetime
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

class Singleton(type):
    def __call__(self, *args, **kwargs):
        if not hasattr(self, '_instance'):
            self._instance = super(Singleton, self).__call__(*args, **kwargs)
#        print 'call: %s' % type(self)
#        if self.__instance is None:
#            self.__instance = super(Singleton, self).__call__(*args, **kwargs)
        if callable(self._instance):
            return self._instance()
        return self._instance

class File( str ):
    #Utility class to allow deletion and terminal printing of files.
    def __new__(self, host, group, path, name, size, db):
        return str.__new__(self, name)
    def __init__(self, host, group, path, name, size, db):
        self.hosts = [host]
        self.group = group
        self.path = path
        self.size = int(size)
        self.db = db
    def pprint(self):
        name = '%s: %s' % (self.hosts[0], os.path.join(self.path, self))
        print u'  {0:<90}{1:>8}'.format(name, human_size(self.size))
    def delete(self):
        be = MythBE(self.hosts[0], db=self.db)
        be.deleteFile(self, self.group)
    def add_host(self, host):
        self.hosts.append(host)

class Recorded( _Recorded ):
    #Utility class to allow deletion and terminal printing of orphaned recording entries.
    def pprint(self):
        name = u'{0.hostname}: {0.title}'.format(self)
        if self.subtitle:
            name += ' - '+self.subtitle
        print u'  {0:<70}{1:>28}'.format(name,self.basename)
    def delete(self, force=False, rerecord=False):
        if self.doubleorphan:
#            self.update(deletepending=0)
            rerecord = False
        super(MyRecorded, self).delete(force, rerecord)
    @property
    def doubleorphan(self):
        return self.deletepending and ((datetime.now - self.lastmodified).days > 1)

def printrecs(title, recs):
    # print out all recordings in list, followed by a count
    if len(recs):
        print title
        for rec in sorted(recs, key=lambda x: x.title):
            rec.pprint()
        print u'{0:>88}{1:>12}'.format('Count:',len(recs))

def printfiles(title, files):
    # print out all files in list, followed by a total size
    if len(files):
        print title
        for f in sorted(files, key=lambda x: x.path):
            f.pprint()
        size = sum([f.size for f in files])
        print u'{0:>88}{1:>12}'.format('Total:',human_size(size))

class populate( object ):
    __metaclass__ = Singleton
    def __init__(self, host=None):
        self.db = MythDB()
        self.db.searchRecorded.handler = Recorded
        self.be = MythBE(db=self.db)
        self.log = MythLog(db=self.db)

        self.set_host(host)
        self.load_backends()
        self.load_storagegroups()

    def set_host(self, host):
        self.host = host
        if host:
            # if the host was defined on the command line, check
            # to make sure such host is defined in the database
            with self.db as c:
                c.execute("""SELECT count(1) FROM settings
                             WHERE hostname=? AND value=?""",
                            (host, 'BackendServerIP'))
                if c.fetchone()[0] == 0:
                    raise Exception('Invalid hostname specified for backend.')

    def load_backends(self):
        with self.db as c:
            c.execute("""SELECT hostname FROM settings
                         WHERE value='BackendServerIP'""")
            hosts = [r[0] for r in c.fetchall()]
        self.hosts = []
        for host in hosts:
            # try to access all defined hosts, and
            # store the ones currently accessible
            try:
                MythBE(backend=host)
                self.hosts.append(host)
            except:
                pass

    def load_storagegroups(self):
        self.storagegroups = \
            [sg for sg in self.db.getStorageGroup() \
                if sg.groupname not in ('Videos','Banners','Coverart',\
                                        'Fanart','Screenshots','Trailers')]

    def flush(self):
        self.misplaced = []
        self.zerorecs = []
        self.pendrecs = []
        self.orphrecs = []
        self.orphvids = []
        self.orphimgs = []
        self.dbbackup = []
        self.unfiltered = []

    def __call__(self):
        self.refresh_content()
        return self

    def refresh_content(self):
        # scan through all accessible backends to
        # generate a new listof orphaned content
        self.flush()

        unfiltered = {}
        for host in self.hosts:
            for sg in self.storagegroups:
                try:
                    dirs,files,sizes = self.be.getSGList(host, sg.groupname, sg.dirname)
                    for f,s in zip(files, sizes):
                        newfile = File(host, sg.groupname, sg.dirname, f, s, self.db)
                        # each filename should be unique among all storage directories
                        # defined on all backends, but may exist in the same directory
                        # on multiple backends if they are shared
                        if newfile not in unfiltered:
                            # add a new file to the list
                            unfiltered[str(newfile)] = newfile
                        else:
                            # add a reference to the host on which it was found
                            unfiltered[str(newfile)].add_host(host)
                except:
                    self.log(MythLog.GENERAL, MythLog.INFO, 
                            'Could not access {0.groupname}@{1}{0.dirname}'.format(sg, host))

        for rec in self.db.searchRecorded(livetv=True):
            if rec.hostname not in self.hosts:
                # recording is on an offline backend, ignore it
                name = rec.basename.rsplit('.',1)[0]
                for n in unfiltered.keys():
                    if name in n:
                        # and anything related to it
                        del unfiltered[n]
            elif rec.basename in unfiltered:
                # run through list of recordings, matching basenames
                # with found files, and removing file from list
                f = unfiltered[rec.basename]
                del unfiltered[rec.basename]
                if f.size < 1024:
                    # file is too small to be of any worth
                    self.zerorecs.append(rec)
                elif rec.doubleorphan:
                    # file is marked for deletion, but has been forgotten by the backend
                    self.pendrecs.append(rec)
                elif rec.hostname not in f.hosts:
                    # recording is in the database, but not where it should be
                    self.misplaced.append(rec)

                name = rec.basename.rsplit('.',1)[0]
                for f in unfiltered.keys():
                    if name in f:
                        # file is related to a valid recording, ignore it
                        del unfiltered[f]
            else:
                # recording has been orphaned
                self.orphrecs.append(rec)

        for n,f in unfiltered.iteritems():
            if n.endswith('.mpg') or n.endswith('.nuv'):
                # filter files with recording extensions
                self.orphvids.append(f)
            elif n.endswith('.png'):
                # filter files with image extensions
                self.orphimgs.append(f)
            elif 'sql' in n:
                # filter for database backups
                self.dbbackup.append(f)
            else:
                self.unfiltered.append(f)

    def print_results(self):
        printrecs("Recordings found on the wrong host", self.misplaced)
        printrecs("Recordings with missing files", self.orphrecs)
        printrecs("Zero byte recordings", self.zerorecs)
        printrecs("Forgotten pending deletions", self.pendrecs)
        printfiles("Orphaned video files", self.orphvids)
        printfiles("Orphaned snapshots", self.orphimgs)
        printfiles("Database backups", self.dbbackup)
        printfiles("Other files", self.unfiltered)

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
    if not sys.stdin.isatty():
        populate().print_results()
        sys.exit(0)

    while True:
        results = populate(host)
        results.print_results()

        opts = [opt for opt in (
                ('Delete orphaned recording entries',     delete_recs,  results.orphrecs),
                ('Delete zero byte recordings',           delete_recs,  results.zerorecs),
                ('Forgotten pending deletion recordings', delete_recs,  results.pendrecs),
                ('Delete orphaned video files',           delete_files, results.orphvids),
                ('Delete orphaned snapshots',             delete_files, results.orphimgs),
                ('Delete other files',                    delete_files, results.unfiltered),
                ('Refresh list',                          None,         None))
                    if (opt[2] is None) or len(opt[2])]
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

if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        main()

