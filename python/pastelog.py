#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
# Name: pastelog.py
# Python Script
# Author: Raymond Wagner
# Purpose
#   This python script is intended to extract MythTV logs from the database
#   and upload them to pastebin websites for further review and assistance.
#---------------------------

import sys

from argparse import ArgumentParser
from collections import namedtuple, OrderedDict
from MythTV.database import DBCache,DBData
from MythTV import MythLog


class EngineType( type ):
    def __new__(mcs, name, bases, attrs):
        cls = type.__new__(mcs, name, bases, attrs)
        if name != 'Engine':
            Engine._engines[name] = cls
            if len(Engine._engines) == 1:
                cls.default = True
            else:
                cls.default = False
        return cls

    def getDefault(cls):
        return cls._engines.keys()[0]

    def getEngines(cls):
        engine = namedtuple('Engine', ['name', 'site', 'default'])
        for name in cls._engines:
            e = cls._engines[name]
            yield engine(name, e.site, e.default)

    def __call__(cls, name):
        return type.__call__(cls._engines[name])

class Engine( object ):
    __metaclass__ = EngineType
    _engines = OrderedDict()
    size = 0

    def post(self, instance):
        instance = list(instance)
        name = instance[0].application + '-' + \
               instance[0].msgtime.strftime('%Y%m%d%H%M%S')

        from cStringIO import StringIO
        s = StringIO()
        count = 1
        for msg in instance:
            if self.size:
                loc = s.tell()

            msg.toFile(s)

            if self.size and (s.tell() > self.size):
                s.seek(loc)
                s.truncate()
                url = self._post(name+'p'+count, s.getvalue())
                print "{0:<40} : {1}".format(name+'p'+count, url)
                count += 1
                s.seek(0)
                s.truncate()
                msg.toFile(s)

        if count > 1:
            name += 'p'+count

        url = self._post(name, s.getvalue())
        print "{0:<40} : {1}".format(name, url)

    def _post(self, name, msg):
        raise NotImplementedError


class Pastebin( Engine ):
    site = "pastebin.com"
    key = "8ee9b3e538215e0f32e7e325164f15b3"
    size = 2**19

    def _post(self, name, msg):
        data = {'api_option':           'paste',
                'api_user_key':         '',
                'api_paste_private':    '1',
                'api_paste_name':       name,
                'api_paste_expire_date':'1M',
                'api_paste_format':     'text',
                'api_dev_key':          self.key,
                'api_paste_code':       msg}

        from urllib import urlencode
        data = urlencode(data)

        from urllib2 import Request, urlopen
        req = Request('http://pastebin.com/api/api_post.php', data)
        res = urlopen(req).read()

        if res[0:3] == 'Bad':
            print res
            sys.exit(1)

        return res

class Log( DBData ):
    _table = 'logging'

    @classmethod
    def getAppNames(cls, hostname=None, db=None):
        app = namedtuple('Application', ['name', 'count'])

        db = DBCache(db)
        if hostname is None:
            hostname = db.gethostname()

        with db as cursor:
            cursor.execute("""SELECT application, count(1)
                                FROM (SELECT DISTINCT application, pid
                                        FROM logging
                                       WHERE host=?) AS `pids`
                               GROUP BY application;""", (hostname,))
            for row in cursor:
                yield app(*row)

    @classmethod
    def getLogs(cls, appname, count, hostname=None, db=None):
        db = DBCache(db)
        if hostname is None:
            hostname = db.gethostname()

        with db as cursor:
            cursor.execute("""SELECT DISTINCT pid
                                FROM logging
                               WHERE application=?
                                 AND host=?
                               ORDER BY id DESC;""", (appname, hostname))
            try:
                instances = zip(*cursor.fetchall())[0]
            except IndexError:
                print "No logs found on system profile."
                sys.exit(1)

        if count == -1:
            count = len(instances)
        else:
            count = min(count, len(instances))
        for pid in instances[0:count]:
            yield list(cls._fromQuery("""WHERE application=?
                                           AND host=?
                                           AND pid=?
                                         ORDER BY id;""",
                                    (appname, hostname, pid)))

    @property
    def nicelevel(self):
        return 'EACEWNID'[self.level]

    def toString(self):
        s = (u"{0.msgtime} {0.nicelevel} [{0.pid}/{0.tid}] {0.thread} "
             u"{0.filename}:{0.line} ({0.function}) - ").format(self)
        offs = len(s)
        for dooffs,msg in enumerate(self.message.split('\n')):
            if dooffs:
                s += u"\n" + u" "*offs
            s += msg
        return s

    def toFile(self, obj):
        obj.write(self.toString() + u"\n")

def main():
    parser = ArgumentParser(
                description=("Utility for extracting and posting " \
                             "MythTV database logs."))

    parser.add_argument('-a', '--application',
                action='append',
                dest='appname',
                help=("Name of MythTV application to pull logs for. " \
                      "This argument can be called multiple times."))
    parser.add_argument('-l', '--list-applications',
                action='store_true',
                dest='showlist',
                help="Show names of applications listed logged in database.")
    parser.add_argument('-p', '--profilename',
                action='store',
                dest='profile',
                help=("Specify system profile to pull logs for. This is "
                      "typically the system hostname."))
    parser.add_argument('-n', '--count',
                action='store',
                type=int,
                dest='count',
                default=1,
                help=("Number of application instances prior to current " \
                      "to pull from the database."))
    parser.add_argument('--engine',
                action='store',
                dest='engine',
                default=Engine.getDefault(),
                help="Pastebin site to upload to.")
    parser.add_argument('--list-engines',
                action='store_true',
                dest='showengines',
                help="Show names of supported Pastebin websites.")

    res = parser.parse_args()

    DB = DBCache()

    if res.showlist:
        print ' -- name --                  -- instance count --'
        for app in Log.getAppNames(res.profile, DB):
            print '{0.name:<30} {0.count:^20}'.format(app)
        sys.exit(0)

    if res.showengines:
        for engine in Engine.getEngines():
            print '{0.name:<20}: {0.site}'.format(engine)
        sys.exit(0)

    if res.appname:
        engine = Engine(res.engine)
        for appname in res.appname:
            for instance in Log.getLogs(appname, res.count, res.profile, DB):
                engine.post(instance)


if __name__ == "__main__":
    main()
