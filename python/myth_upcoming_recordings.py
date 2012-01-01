#!/usr/bin/env python

from datetime import timedelta, datetime
from optparse import OptionParser
from MythTV import MythBE, Program

class MyProgram( Program ):
    @property
    def is_scheduled(self):
        return self.recstatus in (self.rsWillRecord,
                                  self.rsRecording,
                                  self.rsRecorded)
    @property
    def is_duplicate(self):
        return self.recstatus in (self.rsRepeat,
                                  self.rsPreviousRecording,
                                  self.rsCurrentRecording)
    @property
    def is_deactivated(self):
        return self.recstatus in (self.rsInactive,
                                  self.rsTooManyRecordings,
                                  self.rsCancelled,
                                  self.rsAborted,
                                  self.rsNotListed,
                                  self.rsDontRecord,
                                  self.rsLowDiskSpace,
                                  self.rsTunerBusy,
                                  self.rsNeverRecord,
                                  self.rsEarlierShowing,
                                  self.rsLaterShowing)
    @property
    def is_conflict(self):
        return self.recstatus == self.rsConflict

def main(opts):
    MythBE.getPendingRecordings.handler = MyProgram
    be = MythBE()
    now = datetime.now()

    if not opts.plaintext:
        print '<h3>Upcoming Recordings:</h3>'
        print '<div class="schedule">'

    count = 0
    for rec in be.getPendingRecordings():
        if not ((opts.filter&2**0 and rec.is_scheduled) or
                (opts.filter&2**1 and rec.is_duplicate) or
                (opts.filter&2**2 and rec.is_deactivated) or
                (opts.filter&2**3 and rec.is_conflict)):
            continue
        if opts.time and (opts.time < rec.recstartts):
            continue
        if now > rec.recendts:
            continue
        if opts.count and (opts.count <= count):
            break
        count += 1

        if opts.plaintext:
            print '{0} - {1}'.format(rec.starttime.strftime('%m/%d, %I:%M %p'),
                                     rec.callsign)
            if rec.subtitle:
                print '{0.title} - {0.subtitle}'.format(rec)
            else:
                print '{0.title}'.format(rec)
            print rec.description
            print ''
        else:
            print '<a href="#">{0} - {1} - {2}'.format(rec.starttime.strftime('%m/%d, %I:%M %p'),
                                     rec.callsign,
                                     rec.title),
            if rec.subtitle:
                print rec.subtitle,
            print '<br /><span><strong>{0.title}</strong>'.format(rec),
            print rec.starttime.strftime('%m/%d, %I:%M %p'),
            print '<br /><em>{0.description}<br/></span></a><hr />'

    if not opts.plaintext:
        print '</div>'


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options]")

    parser.add_option('-n', "--count", action="store", type="int",
            default=0, dest="count",
            help="Outputs information on the next <count> shows to be recorded.")
    parser.add_option("--hours", action="store", type="int",
            default=-1, dest="hours",
            help="Outputs information for recordings starting within the next "+\
                 "specified hours.")
    parser.add_option("--minutes", action="store", type="int",
            default=-1, dest="minutes",
            help="Outputs information for recordings starting within the next "+\
                 "specified minutes.")
    parser.add_option("--show-scheduled", action="store_true", default=False,
            dest="scheduled",
            help="Outputs information about recordings MythTV plans to actually "+\
                 "record.")
    parser.add_option("--show-duplicates", action="store_true", default=False,
            dest="duplicate",
            help="Outputs information about recordings MythTV will not record "+\
                 "because of the specified duplicate matching policy for that rule")
    parser.add_option("--show-deactivated", action="store_true", default=False,
            dest="deactivated",
            help="Outputs information on shows that are deactivated and will not "+\
                 "be recorded by MythTV.  This may be due to the schedule being "+\
                 "inactive, being set to never record, because the show will be "+\
                 "recorded at an earlier or later date, because there are too many "+\
                 "recordings on that rule, because there is insufficient disk space, "+\
                 "or because the show is not in the time slot listed by the rule.")
    parser.add_option("--show-conflicts", action="store_true", default=False,
            dest="conflicts",
            help="Outputs information on shows that will not be recorded due to "+\
                 "higher priority conflicts.")
    parser.add_option("--plain-text", action="store_true", default=False,
            dest="plaintext", help="Output data in plain text format.")

    opts, args = parser.parse_args()

    if opts.scheduled or opts.duplicate or opts.deactivated or opts.conflicts:
        opts.filter = opts.scheduled*2**0 | \
                      opts.duplicate*2**1 | \
                      opts.deactivated*2**2 | \
                      opts.conflicts*2**3
    else:
        opts.filter = 2**0 or 2**3

    if (opts.hours >= 0) or (opts.minutes >= 0):
        opts.time = datetime.now() + timedelta(
                            hours=opts.hours if (opts.hours >= 0) else 0,
                            minutes=opts.minutes if (opts.minutes >= 0) else 0)
    else:
        opts.time = None

    main(opts)
