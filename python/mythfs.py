#!/usr/bin/env python

try:
    import _find_fuse_parts
except ImportError:
    pass
import re
import errno
import stat
import os
import sys
from time import mktime, sleep
from datetime import date
from traceback import format_exc
from weakref import proxy

try:
    import fuse
except:
    print 'Warning! FUSE Python bindings could not be found'
    sys.exit(1)
if not hasattr(fuse, '__version__'):
    print 'Warning! Installed FUSE Python bindings are too old.'
    sys.exit(1)
from fuse import Fuse

try:
    import MythTV
except:
    print 'Warning! MythTV Python bindings could not be found'
    sys.exit(1)
if MythTV.__version__ < (0,24,0,0):
    print 'Warning! Installed MythTV Python bindings are tool old. Please update'
    print '    to 0.23.0.18 or later.'
    sys.exit(1)
from MythTV import MythDB, MythVideo, ftopen, MythBE,\
                   Video, Recorded, MythLog, static

fuse.fuse_python_api = (0, 2)
LOG = MythLog(lstr='none')
MythLog._setfile('/dev/null')
BACKEND = None

def doNothing(*args, **kwargs):
    pass

def increment():
    res = 1
    while True:
        yield res
        res += 1

class Attr(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_blksize = 0
        self.st_nlink = 1
        self.st_uid = os.getuid()
        self.st_gid = os.getgid()
        self.st_blocks = 1
        self.st_rdev = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

class Directory(object):
    def __str__(self):
        return "<Directory '%s' at %s>" % (self.path, hex(id(self)))
    def __repr__(self):
        return "<Directory '%s' at %s>" % (self.path, hex(id(self)))
    def __init__(self, path):
        self.path = path
        self.attr = Attr()
        self.attr.st_mode = stat.S_IFDIR | 0555
        self.children = []

    def addChild(self, name, attr):
        self.children.append(name)
        LOG(LOG.FILE, "adding child to '%s'" % self.path, name)
        self.attr.st_size += 1
        if (self.attr.st_ctime > attr.st_ctime) or (self.attr.st_size == 1):
            self.attr.st_ctime = attr.st_ctime
        if (self.attr.st_mtime < attr.st_mtime) or (self.attr.st_size == 1):
            self.attr.st_mtime = attr.st_mtime
        if (self.attr.st_atime < attr.st_atime) or (self.attr.st_size == 1):
            self.attr.st_atime = attr.st_atime

class Handler( object ):
    def getAll(self):
        # provides an iterable of all initial objects
        # if inode needs to be known, a generator can be used
        #   and the inode pulled from the object
        return iter([])

    def setFormat(self, fmt):
        # called with a string of additional data passed on the
        #   mount call to control the behavior of the mount
        pass

    def _openHandler(self, inode):
        # called with the object when one is opened
        pass

    def _closeHandler(self, inode):
        # called with the object when one is closed
        pass

    def _deleteHandler(self, inode):
        # called with the object when one is deleted
        # raising a NotImplementedError will cause deletions
        #   to be disallowed
        raise NotImplementedError

class Single( Handler ):
    class FileObj( object ):
        def __init__(self, path, db=None):
            self.path = path
            self.db = MythDB(db=db)
        def open(self, mode):
            return ftopen(path, mode, db=self.db)

    def __init__(self):
        self.db = MythDB()
        self.be = MythBE(db=self.db)

    def getAll(self):
        reuri = re.compile('myth://((?P<group>.*)@)?(?P<host>[a-zA-Z0-9_\.]*)(:[0-9]*)?/(?P<file>.*)')
        match = reuri.match(self.uri)
        group,host,filename = match.groups()
        t,s = be.getSGFile(host, group, filename)

        obj = self.FileObj(self.file, db)
        obj.attr = Attr()
        obj.attr.st_mode = stat.S_IFREG | 0444
        obj.attr.st_size = int(s)
        self._addCallback(obj)

    def setFormat(self, fmt):
        self.uri = fmt

class Videos( Handler ):
    def __init__(self):
        self.db = MythDB()
        self.be = MythBE(db=db)
        self.vids = {}
        self._addCallback = doNothing
        self._events = [self.handleUpdate]
        self.be.registerevent(self.handleUpdate)

    def add(self, vid):
        if not vid.browse:
            return
        if vid.intid in self.vids:
            return

        vid.path = vid.filename
        vid.attr = Attr()
        try:
            ctime = vid.insertdate.timestamp()
        except:
            ctime = 0
        vid.attr.st_ctime = ctime
        vid.attr.st_atime = atime
        vid.attr.st_mtime = ctime
        vid.attr.st_mode = stat.S_IFREG | 0444
        t,s = self.be.getSGFile(vid.host, 'Videos', vid.filename)
        vid.attr.st_size = int(s)

        self._addCallback(vid)
        self.vids[vid.intid] = vid.attr.st_ino

    def getAll(self):
        for vid in Video.getAllEntries(db=self.db):
            self.add(vid)

    def handleUpdate(self, event=None):
        if event is None:
            self._reUp = re.compile(
                    re.escape(static.BACKEND_SEP).\
                        join(['BACKEND_MESSAGE',
                              'VIDEO_LIST_CHANGE',
                              'empty']))
            return self._reUp
        with self.db as cursor:
            cursor.execute("""SELECT intid FROM videometadata""")
            newids = [id[0] for id in cursor.fetchall()]

        oldids = self.vids.keys()
        for id in list(oldids):
            if id in newids:
                oldids.remove(id)
                newids.remove(id)

        for id in oldids:
            self._deleteCallback(self.vids[id])
        for id in newids:
            self.add(Video(id, db=self.db))

class Recordings( Handler ):
    def __init__(self):
        self.be = MythBE()
        self.recs = {}
        self._events = [self.handleAdd, self.handleDelete, self.handleUpdate]
        for e in self._events:
            self.be.registerevent(e)

    def add(self, rec):
        # check for duplicates
        match = (str(rec.chanid),rec.recstartts.isoformat())
        if match in self.recs:
            return

        # add attributes
        rec.attr = Attr()
        ctime = rec.lastmodified.timestamp()
        rec.attr.st_ctime = ctime
        rec.attr.st_mtime = ctime
        rec.attr.st_atime = ctime
        rec.attr.st_size = rec.filesize
        rec.attr.st_mode = stat.S_IFREG | 0444

        # process name
        rec.path = rec.formatPath(self.fmt, ' ')

        # add file
        self._addCallback(rec)
        self.recs[match] = rec.attr.st_ino

    def genAttr(self, rec):
        attr = Attr()
        ctime = rec.lastmodified.timestamp()
        attr.st_ctime = ctime
        attr.st_mtime = ctime
        attr.st_atime = ctime
        attr.st_size = rec.filesize
        attr.st_mode = stat.S_IFREG | 0444
        return attr

    def getAll(self):
        for rec in self.be.getRecordings():
            self.add(rec)

    def handleAdd(self, event=None):
        if event is None:
            self._reAdd = re.compile(
                    re.escape(static.BACKEND_SEP).\
                        join(['BACKEND_MESSAGE',
                              'RECORDING_LIST_CHANGE ADD '
                                  '(?P<chanid>[0-9]*) '
                                  '(?P<starttime>[0-9-]*T[0-9:]*)',
                              'empty']))
            return self._reAdd
        LOG(LOG.FILE, 'add event received', event)

        match = self._reAdd.match(event).groups()
        if match in self.recs:
            return

        rec = self.be.getRecording(match[0], match[1])
        self.add(rec)

    def handleDelete(self, event=None):
        if event is None:
            self._reDel = re.compile(
                    re.escape(static.BACKEND_SEP).\
                        join(['BACKEND_MESSAGE',
                              'RECORDING_LIST_CHANGE DELETE '
                                  '(?P<chanid>[0-9]*) '
                                  '(?P<starttime>[0-9-]*T[0-9:]*)',
                              'empty']))
            return self._reDel
        LOG(LOG.FILE, 'delete event received', event)

        match = self._reDel.match(event).groups()
        if match not in self.recs:
            return

        self._deleteCallback(self.recs[match])
        del self.recs[match]

    def handleUpdate(self, event=None):
        if event is None:
            self._reUp = re.compile(
                    re.escape(static.BACKEND_SEP).\
                        join(['BACKEND_MESSAGE',
                              'UPDATE_FILE_SIZE '
                                  '(?P<chanid>[0-9]*) '
                                  '(?P<starttime>[0-9-]*T[0-9:]*) '
                                  '(?P<size>[0-9]*)',
                              'empty']))
            return self._reUp
        LOG(LOG.FILE, 'update event received', event)

        match = self._reUp.match(event)
        size = match.group(3)
        match = match.group(1,2)
        if match not in self.recs:
            return

        inode = self.recs[match]
        rec = self._inodeCallback(inode)
        rec.filesize = int(size)
        rec.attr.st_size = int(size)

    def setFormat(self, fmt):
        if '%' not in fmt:
            LOG(LOG.FILE, 'pulling format from database', 'mythfs.format.%s' % fmt)
            fmt = self.be.db.settings.NULL['mythfs.format.%s' % fmt]
        LOG(LOG.FILE, 'using format', fmt)
        self.fmt = fmt

class MythFS( Fuse ):
    _nextInode = increment()

    def __init__(self, *args, **kw):
        Fuse.__init__(self, *args, **kw)
        self._inode = {}
        self._paths = {}
        self._openFiles = {}

    def fsinit(self):
        fmt = self.parser.largs[0].split(',',1)
        LOG(LOG.FILE, 'starting mythfs', str(fmt))
        self._add(Directory(''))
        try:
            LOG(LOG.FILE, 'running', '%s()' % fmt[0])
            self._handler = eval('%s()' % fmt[0])
        except:
            LOG(LOG.FILE, 'no file handler for',fmt[0])
            raise Exception('No file handler for given mount.')
        if len(fmt) == 2:
            self._handler.setFormat(fmt[1])
        self._handler._addCallback = self._add
        self._handler._deleteCallback = self._delete
        self._handler._inodeCallback = self._getObjIno
        self._handler.getAll()

    def _getObjIno(self, inode):
        return self._inode[inode]

    def _getObjPth(self, path):
        return self._inode[self._paths[path.strip('/')]]

    def _add(self, newfile):
        LOG(LOG.FILE, 'adding file', str(newfile))
        # add entries for new file
        path = newfile.path.strip('/')
        inode = self._nextInode.next()
        newfile.attr.st_ino = inode

        if path in self._paths:
            LOG(LOG.FILE, 'filename already in use', path)
            p = path.rsplit('.',1)
            i = 1
            while path in self._paths:
                path = '.'.join((p[0], str(i), p[1]))
                LOG(LOG.FILE, '    trying replacement', path)
                i += 1
            LOG(LOG.FILE, '    replacement found', path)
            newfile.path = path
        self._paths[path] = inode
        self._inode[inode] = newfile
        newfile.attr.st_ino = inode

        # increment directory size, or add new
        if path == '':
            return
        if '/' not in path:
            parent,child = '',path
        else:
            parent,child = path.rsplit('/',1)
        LOG(LOG.FILE, 'adding child (%s) to parent (%s)' % (child, parent))
        if parent in self._paths:
            parent = self._getObjPth(parent)
            parent.addChild(child, newfile.attr)
        else:
            LOG(LOG.FILE, 'parent not found, adding new', "'%s'" % parent)
            parent = Directory(parent)
            parent.addChild(child, newfile.attr)
            self._add(parent)

    def _delete(self, inode):
        path = self._getObjIno(inode).path
        # do not delete the root
        if path == '':
            return

        # delete references to entry
        del self._paths[path]
        del self._inode[inode]

        # update parents
        if '/' in path:
            parent,child = path.rsplit('/',1)
        else:
            parent,child = '',path
        parent = self._getObjPth(parent)
        parent.children.remove(child)
        parent.attr.st_size -= 1
        if parent.attr.st_size == 0:
            self._delete(self._paths[parent.path])

    def readdir(self, path, offset):
        LOG(LOG.FILE, 'requesting directory listing', path)
        d = self._getObjPth(path)
        LOG(LOG.FILE, '   listing...', str(d.children))
        r = tuple([fuse.Direntry(e) for e in d.children])
        LOG(LOG.FILE, '   listing...', str(r))
        return tuple([fuse.Direntry(str(e)) for e in d.children])

    def getattr(self, path):
        LOG(LOG.FILE, 'requesting attributes', path)
        a = self._getObjPth(path).attr
        LOG(LOG.FILE, '    ', str(a.__dict__.items()))
        return self._getObjPth(path).attr

    def open(self, path, flags):
        LOG(LOG.FILE, 'requesting file open', path)
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

        if path not in self._openFiles:
            f = self._getObjPth(path)
            self._openFiles[path] = [1, f.open()]
            self._handler._openCallback(f)
        else:
            self._openFiles[path][0] += 1
        LOG(LOG.FILE, 'open files', str(self._openFiles))

    def read(self, path, length, offset, fh=None):
        LOG(LOG.FILE, 'requesting file read', '%s, %d, %d' % (path,length,offset))
        if path not in self._openFiles:
            return -errno.ENOENT
        f = self._openFiles[path][1]
        if f.tell() != offset:
            f.seek(offset)
        return f.read(length)

    def release(self, path, fh=None):
        LOG(LOG.FILE, 'requesting file close', path)
        if path in self._openFiles:
            self._openFiles[path][0] -= 1
            if self._openFiles[path][0] == 0:
                self._openFiles[path][1].close()
                del self._openFiles[path]
                self._handler._deleteCallback(self._getObjPth(path))
        else:
            return -errno.ENOENT

    def unlink(self, path):
        self._handler._deleteCallback(self._getObjPth(path))

class DebugFS( MythFS ):
    class Parser( object ):
        def __init__(self):
            self.largs = sys.argv[1:]
        
    def __init__(self, *args, **kwargs):
        self._inode = {}
        self._paths = {}
        self._openFiles = {}
        self.parser = self.Parser()

def store_format():
    i = iter(sys.argv)
    while i.next() != '--storeformat':
        pass
    tag = i.next()
    fmt = i.next()
    db = MythDB()
    db.settings.NULL['mythfs.format.%s' % tag] = fmt
    sys.exit()

def print_formats():
    db = MythDB()
    print '    Label        Format '
    print '    -----        ------ '
    with db as cursor:
        cursor.execute("""SELECT value,data FROM settings WHERE value like 'mythfs.format.%'""")
        for lbl,fmt in cursor.fetchall():
            lbl = lbl[14:]
            print '%s %s' % (lbl.center(16), fmt)
    sys.exit()

def print_help():
    print """usage: mythfs.py mode[#format] /mount/point [-o some,options]
  allowed modes are:
      Recordings,format - outputs all recordings
                          also accepts stored format names
      Videos            - outputs all MythVideo content
      Single,myth://... - outputs a single file
  other options:'
      --help            - print this
      --helpformat      - print a description of allowed format tags
      --listformats     - list all named formats stored in the database
      --storeformat <name> <format>
                        - store a new format to the database
"""
    sys.exit()

def print_format_help():
    print 'need to put stuff here'
    sys.exit()
    
def run_debug():
    MythLog._setfile('/var/log/mythtv/mythfs.log')
    MythLog._setlevel('important,general,file')
    fs = DebugFS()
    fs.fsinit()
    banner = 'MythTV Python interactive shell.'
    import code
    try:
        import readline, rlcompleter
    except:
        pass
    else:
        readline.parse_and_bind("tab: complete")
        banner += ' TAB completion available.'
    namespace = globals().copy()
    namespace.update(locals())
    code.InteractiveConsole(namespace).interact(banner)
    sys.exit()


def main():
    fs = MythFS(version='MythFS 0.24.0', usage='', dash_s_do='setsingle')
    fs.parse(errex=1)
    fs.flags = 0
    fs.multithreaded = True
    fs.main()

LOG(LOG.FILE, str(sys.argv))
if __name__ == '__main__':
    for arg in sys.argv:
        if arg == '--storeformat':
            store_format()
        if arg == '--listformats':
            print_formats()
        if arg == '--helpformat':
            print_format_help()
        if arg == '--help':
            print_help()
        if arg == '--debug':
            run_debug()
    main()

