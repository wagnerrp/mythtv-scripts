#!/usr/bin/env python
from MythTV import MythDB, MythError, MythLog, Frontend

from datetime import datetime, timedelta
from curses   import wrapper, ascii
from time     import sleep
import sys, socket, curses, re

#note for ticket, on-screen-keyboard remotely does not have focus

MythLog._setlevel('none')
frontend = None

rplaytype = re.compile('Playback ([a-zA-Z]+)')
rrecorded = re.compile('Playback ([a-zA-Z]+) ([\d:]+) of ([\d:]+) ([-0-9\.]+x) (\d*) ([0-9-T:]+)')
rlivetv   = rrecorded
rvideo    = re.compile('Playback [a-zA-Z]+ ([\d:]+) ([-0-9\.]+x) .*/(.*) \d+ [\.\d]+')
rrname    = re.compile('\d+ [0-9-T:]+ (.*)')
rlname    = re.compile('\d+ [0-9-T: ]+ (.*)')

def align(side, window, y, string, flush=0):
    w = window.getmaxyx()[1]-1
    if len(string) > w:
        string = string[:w]
    if side == 0:
        x = 1
    elif side == 1:
        x = (w-len(string))/2+1
    elif side == 2:
        x = w-len(string)
    window.addstr(y,x,string)

def query_time(w, _dat=[0]):
    if _dat[0] == 0:
        ltime   = datetime.now()
        fetime  = frontend.getTime()
        _dat[0] = fetime - ltime
    time = datetime.now()+_dat[0]
    w.erase()
    w.border(curses.ACS_VLINE,    curses.ACS_VLINE,
             curses.ACS_HLINE,    curses.ACS_HLINE,
             curses.ACS_ULCORNER, curses.ACS_TTEE,
             curses.ACS_LTEE,     curses.ACS_RTEE)
    align(1,w,1,time.strftime('%H:%M:%S'))
    w.noutrefresh()

def query_load(w, _dat=[0]):
    if _dat[0] == 0:
        _dat[0] = datetime.now()
    now = datetime.now()
    if _dat[0] > now:
        return
    _dat[0] = now+timedelta(seconds=5)

    loads = frontend.getLoad()
    w.erase()
    w.border(curses.ACS_VLINE,    curses.ACS_VLINE,
             curses.ACS_HLINE,    curses.ACS_HLINE,
             curses.ACS_LTEE,     curses.ACS_RTEE,
             curses.ACS_LTEE,     curses.ACS_RTEE)
    align(0,w,2,'loads')
    align(2,w,1,' 1: {0:0.2f}'.format(loads[0]))
    align(2,w,2,' 5: {0:0.2f}'.format(loads[1]))
    align(2,w,3,'15: {0:0.2f}'.format(loads[2]))
    w.noutrefresh()

def query_loc(w, _dat=[0]):
    if _dat[0] == 0:
        _dat[0] = datetime.now()
    now = datetime.now()
    if _dat[0] > now:
        return
    _dat[0] = now+timedelta(seconds=5)

    loc = frontend.sendQuery('location')
    pb = rplaytype.match(loc)
    w.erase()
    w.border(curses.ACS_VLINE,    curses.ACS_VLINE,
             curses.ACS_HLINE,    curses.ACS_HLINE,
             curses.ACS_TTEE,     curses.ACS_URCORNER,
             curses.ACS_BTEE,     curses.ACS_LRCORNER)
    if pb:
        if pb.group(1) == 'Video':
            pb = rvideo.match(loc)
            align(0,w,1,'  Playback: %s' % pb.group(3))
            align(0,w,2,'     %s @ %s' % (pb.group(1),pb.group(2)))
        else:
            pb = rrecorded.match(loc)
            if pb.group(1) == 'Recorded':
                show = frontend.sendQuery('recording %s %s' \
                                            % (pb.group(5),pb.group(6)))
                name = rrname.match(show).group(1)
                align(0,w,1,'  Playback: %s' % name)
                
            elif pb.group(1) == 'LiveTV':
                show = frontend.sendQuery('liveTV %s' % pb.group(5))
                name = rlname.match(show).group(1)
                align(0,w,1,'  LiveTV: %s - %s' % (pb.group(5),name))
            align(0,w,2,'      %s of %s @ %s' \
                                % (pb.group(2),pb.group(3),pb.group(4)))
    else:
        align(0,w,1,'  '+loc)
    w.noutrefresh()

def query_mem(w, _dat=[0]):
    if _dat[0] == 0:
        _dat[0] = datetime.now()
    now = datetime.now()
    if _dat[0] > now:
        return
    _dat[0] = now+timedelta(seconds=15)

    mem = frontend.getMemory()
    w.erase()
    w.border(curses.ACS_VLINE,    curses.ACS_VLINE,
             curses.ACS_HLINE,    curses.ACS_HLINE,
             curses.ACS_LTEE,     curses.ACS_RTEE,
             curses.ACS_LLCORNER, curses.ACS_BTEE)
    align(0,w,1,'phy:')
    align(0,w,2,'swp:')
    align(2,w,1,"%sM/%sM" % (mem['freemem'],mem['totalmem']))
    align(2,w,2,"%sM/%sM" % (mem['freeswap'],mem['totalswap']))
    w.noutrefresh()

def main(w):
    curses.halfdelay(10)
    frontend.connect()
    y,x = w.getmaxyx()

    mem = w.derwin(4,20,9,0)
    query_mem(mem)

    load = w.derwin(5,20,5,0)
    query_load(load)

    conn = w.derwin(4,20,2,0)
    align(2,conn,1,frontend.host)
    align(2,conn,2,"%s:%d" % frontend.socket.getpeername())
    conn.border(curses.ACS_VLINE,    curses.ACS_VLINE,
                curses.ACS_HLINE,    curses.ACS_HLINE,
                curses.ACS_LTEE,     curses.ACS_RTEE,
                curses.ACS_LTEE,     curses.ACS_RTEE)

    time = w.derwin(3,20,0,0)
    query_time(time)

    loc = w.derwin(13,x-20,0,19)
    loc.timeout(1)
    while True:
        a = None
        s = None
        try:
            query_time(time)
            query_load(load)
            query_loc(loc)
            query_mem(mem)
            align(1,w,0,' MythFrontend Remote Socket Interface ')
            curses.doupdate()

            a = w.getch()
            curses.flushinp()
            frontend.key[a]
        except KeyboardInterrupt:
            break
        except EOFError:
            break
        except MythError:
            print "Remote side closed connection..."
            break
        except:
            raise

if __name__ == '__main__':
    if len(sys.argv) == 2:
        try:
            db = MythDB()
            frontend = db.getFrontend(sys.argv[1])
            wrapper(main)
        except socket.timeout:
            print "Could not connect to "+sys.argv[1]
            pass
        except TypeError:
            print sys.argv[1]+" does not exist"
            pass
        except KeyboardInterrupt:
            sys.exit()
        except:
            raise
    else:
        print "Please choose from the following available frontends:"
        frontends = None
        while frontend is None:
            if frontends is None:
                frontends = list(Frontend.fromUPNP())
                if len(frontends) == 0:
                    print "No frontends detected"
                    sys.exit()
            for i,f in enumerate(frontends):
                print "%d. %s" % (i+1, f)
            try:
                i = int(raw_input('> '))-1
                if i in range(0,len(frontends)):
                    frontend = frontends[i]
                    wrapper(main)
            except KeyboardInterrupt:
                sys.exit()
            except EOFError:
                sys.exit()
            except:
                raise
                print "This input will only accept a number. Use Crtl-C to exit"

