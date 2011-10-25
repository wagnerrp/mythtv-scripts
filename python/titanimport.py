#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
# Name: titanimport.py
# Python Script
# Author: Raymond Wagner
# Purpose
#   This python script is to be run by a browser to handle downloaded tvpi
#   files from TitanTV, importing them as scheduling rules for MythTV to
#   record
#---------------------------

__title__  = "TitanImport"
__author__ = "Raymond Wagner"
__version__= "v0.1.0"

from MythTV import MythDB, MythBE, Channel, Record, datetime
from datetime import timedelta
from optparse import OptionParser

import lxml.etree as etree

DB = MythDB()
BE = MythBE(db=DB)
tzoff = timedelta(0, int(BE.backendCommand('QUERY_TIME_ZONE').split('[]:[]')[1]))

def FindProgram(xmlprog, fuzzy):
    tvmode = xmlprog.find('tv-mode').text
    chan = None
    if tvmode == 'cable':
        # for cable, require a match of channel and station name
        for c in Channel.getAllEntries(db=DB):
            if c.freqid == xmlprog.find('rf-channel').text and \
               c.mplexid == 32767 and \
               c.callsign == xmlprog.find('station').text:
                chan = c
                break
        else:
            if not fuzzy:
                return None
    elif tvmode in ('digital_cable', 'satellite'):
        # for digital cable and satellite, use station name only
        for c in Channel.getAllEntries(db=DB):
            if c.callsign == xmlprog.find('station').text:
                chan = c
                break
        else:
            if not fuzzy:
                return None
    elif tvmode == 'digital':
        # for broadcast digital, go with PSIP channel
        # fall back to physical channel and stream id
        for c in Channel.getAllEntries():
            if c.atsc_major_chan == int(xmlprog.find('psip-major').text) and \
               c.atsc_major_chan == int(xmlprog.find('psip-minor').text):
                chan = c
                break
        else:
            for c in Channel.getAllEntries(db=DB):
                if c.freqid == xmlprog.find('rf-channel').text and \
                   c.serviceid == xmlprog.find('stream-number').text:
                    chan = c
                    break
            else:
                if not fuzzy:
                    return None

    starttime = datetime.duck(xmlprog.find('start-date').text +\
                              xmlprog.find('start-time').text.replace(':','') +\
                              '00') + tzoff
    endtime = datetime.duck(xmlprog.find('end-date').text +\
                            xmlprog.find('end-time').text.replace(':','') +\
                            '00') + tzoff
    title = xmlprog.find('program-title').text
    try: subtitle = xmlprog.find('episode-title').text
    except AttributeError: subtitle = None

    if chan:
        # there should only be one response to the query
        try:
            prog = DB.searchGuide(chanid = chan.chanid,
                                  startafter = starttime-timedelta(0,300),
                                  startbefore = starttime+timedelta(0,300),
                                  endafter = endtime-timedelta(0,300),
                                  endbefore = endtime+timedelta(0,300)).next()
        except StopIteration:
            return None

        if prog.title == xmlprog.find('program-title').text:
            if not subtitle:
                # direct movie match
                return prog
            if prog.subtitle == subtitle:
                # direct television match
                return prog
            if fuzzy:
                # close enough
                return prog
        return None

    else:
        progs = list(DB.searchGuide(title = xmlprog.find('program-title').text,
                                    startafter = starttime-timedelta(0,300),
                                    startbefore = starttime+timedelta(0,300),
                                    endafter = endtime-timedelta(0,300),
                                    endbefore = endtime+timedelta(0,300)))
        if len(progs) == 0:
            return None

        if not subtitle:
            # nothing that can be used to better match, just pick the first
            return progs[0]

        for prog in progs:
            if prog.subtitle == subtitle:
                # best option
                return prog
        else:
            # no direct match, just pick the first
            return progs[0]

def main():
    parser = OptionParser(usage="usage: %prog [options] <tvpi file> [<tvpi file> [...]]")

    parser.add_option("-f", "--fuzzy", action="store_true", default=False, dest="fuzzy",
            help="Record something with matching program title in that timeslot if "+\
                 "episode or station information does not match")
    parser.add_option("-s", "--simulation", action="store_true", default=False, dest="sim",
            help="Find matching recording and print out, but do not create new rule")
    parser.add_option("-i", "--intelligent", action="store_true", default=False, dest="smart",
            help="Use a 'record one' rule, rather than 'record specific', to allow the "+\
                 "scheduler to deal with conflicting recordings intelligently")
    parser.add_option("-p", "--priority", action="store", type="int", default=0, dest="priority",
            help="Specify recording priority for purposes of conflict resolution")

    opts, args = parser.parse_args()

    for arg in args:
        print "Reading "+arg
        with open(arg) as f:
            xml = etree.parse(f)

        for xmlprog in xml.getroot().iterfind("program"):
            prog = FindProgram(xmlprog, opts.fuzzy)
            if not prog:
                print "No matching guide data for {0} found"\
                            .format(xmlprog.find('program-title').text)
                continue

            print "Adding rule for {0} on {1} at {2}"\
                            .format(prog.title, Channel(prog.chanid).callsign,
                                    prog.starttime.isoformat())
            if not opts.sim:
                if opts.smart:
                    rec = Record.fromPowerRule("{0.title} ({0.subtitle})".format(prog),
                            where = 'program.title = ? AND program.subtitle = ?',
                            args = (prog.title, prog.subtitle),
                            type = Record.kFindOneRecord,
                            db = DB)
                else:
                    rec = Record.fromGuide(prog, Record.kSingleRecord)
                if opts.priority:
                    rec.recpriority = opts.priority
                    rec.update()

if __name__ == '__main__':
    main()
