#!/usr/bin/env python
#
#
import getopt, sys, string
import xmlrpclib

command = "status"
device = ''
volume = 50
uri = ''

try:
    optlist, args = getopt.getopt( sys.argv[1:], "c:d:v:u:", ['command=', 'device=', 'volume=', 'uri='])
except getopt.GetoptError:
    print "falsche parameter"
    sys.exit(1)  

for option, param in optlist:
    if option in( '-c', '--command'):command=param
    if option in( '-d', '--device'):device=param
    if option in( '-v', '--volume'):volume=param
    if option in( '-u', '--uri'):uri=param
    
s = xmlrpclib.Server('http://127.0.0.1:31020/')

if( command == "ping"):
    r=s.ping()
    
if( command == "list_devices"):
    r=s.list_devices()

if( command == "mute" and device != ''):
    r=s.mute_device(device)

if( command == "unmute" and device != ''):
    r=s.unmute_device(device)

if( command == "set_volume" and device != ''):
    r=s.set_volume(device, volume)

if( command == "play" and device != ''):
    r=s.play(device)

if( command == "pause" and device != ''):
    r=s.pause(device)

if( command == "stop" and device != ''):
    r=s.stop(device)

if( command == "next" and device != ''):
    r=s.next(device)
    
if( command == "previous" and device != ''):
    r=s.previous(device)
    
if( command == "set_av_transport_uri" and device != '' and uri != ''):
    r=s.set_av_transport_uri(device, uri)
    
if( command == "shutdown"):
    r=s.shutdown()

print r
