#!/usr/bin/env python

import re
import sys
from MythTV import DBData
from optparse import OptionParser

class Log( DBData ):
    _table = 'logging'
    _re_process = re.compile('(Started|Tuning) '+\
                  'recording: (?P<title>(".*"|[^ ]*))'+\
                           '(:(?P<subtitle>(".*"|[^ ]*)))?: '+\
                     'channel (?P<channel>[0-9]+) '+\
                   'on cardid (?P<cardid>[0-9]+), '+\
                    'sourceid (?P<sourceid>[0-9]+)')

    @classmethod
    def getRecordings(cls, count):
        logs = []
        for log in cls._fromQuery("""WHERE thread=?
                                       AND message LIKE ?""",
                            ('Scheduler', '%recording:%')):
            match = log._re_process.match(log.message)
            log.title    = match.group('title')
            log.subtitle = match.group('subtitle')
            log.channel  = match.group('channel')
            log.cardid   = match.group('cardid')
            log.sourceid = match.group('sourceid')
            logs.append(log)
        logs.sort(key=lambda l: l.msgtime, reverse=True)
        if count:
            if len(logs) > count:
                return logs[:count]
        return logs
        

    def Print(self, out):
        if self.subtitle is not None:
            show = '{0.title}: {0.subtitle}'.format(self)
        else:
            show = self.title

        if self.format == 'HTML':
            out.write('<a href="#">')
            out.write(  '{0.msgtime} - {1} - Capture Card: {0.cardid}'.format(self, show))
            out.write(  '<br />')
            out.write(  '<span>')
            out.write(    '<strong>{0.title}</strong>'.format(self))
            out.write(    ' {0.msgtime}'.format(self))
            out.write(    '<br />')
            if self.subtitle is not None:
                out.write('<em>{0.subtitle}</em>'.format(self))
            out.write(    '<br /><br />')
            out.write(    'Channel ID: {0.channel}<br />'.format(self))
            out.write(    'Capture Card ID: {0.cardid}<br />'.format(self))
            out.write(    'Video Source ID: {0.sourceid}<br />'.format(self))
            out.write(  '</span>')
            out.write('</a>')
        elif self.format == 'TEXT':
            out.write('{0.msgtime} - {1}\n\n'.format(self, show))
            out.write(' - Capture Card ID: {0.cardid}\n'.format(self))
            out.write(' - Video Source ID: {0.sourceid}\n'.format(self))
            out.write(' -      Channel ID: {0.channel}\n'.format(self))
        else:
            raise Exception('invalid print format')

if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option('--text', action="store_true", default=False, dest="text",
            help="Print recordings in plain text.")
    parser.add_option('--html', action="store_true", default=True, dest="html",
            help="Print recordings in formatted HTML.")
    parser.add_option('-n', '--limit', action="store", type='int', dest="count", default=0,
            help="Limit printout to last <n> recordings.")

    opts, args = parser.parse_args()
    if opts.text:
        Log.format = 'TEXT'
    elif opts.html:
        Log.format = 'HTML'

    if opts.html:
        sys.stdout.write('<h3>Capture Information</h3>\n')
        sys.stdout.write('<div class="schedule">\n')
    for log in Log.getRecordings(opts.count):
        log.Print(sys.stdout)
        if opts.html:
            sys.stdout.write('<hr />\n')
    if opts.html:
        sys.stdout.write('</div>\n')
