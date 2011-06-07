#! /usr/bin/python

import sys
import socket
import ConfigParser
import string
from threading import Timer
from string import atoi, atof

#udp send_packet function
def send_packet(udp_ip, udp_port, pcount):
    count = 0
    while(pcount) :
        pcount = pcount - 1
        sock = socket.socket( socket.AF_INET, # Internet
                              socket.SOCK_DGRAM ) # UDP
        sock.sendto(str(count), (udp_ip, udp_port) )
        count+=1
        print udp_ip + ':' + str(udp_port) + ":" + str(count) + "th packet sent"

#config_path
config_path = ""
if len(sys.argv) > 1 :
    config_path = sys.argv[1] 
else :
    config_path = "Netflix_Server.cfg"

config = ConfigParser.RawConfigParser()
config.read(config_path)

ip = config.get('Server', 'ip')
port = config.getint('Server', 'port')

print 'Starting server at %s:%d'%(ip, port)

#read play log
f = open('Netflix_Server.log')
lines = f.readlines()
f.close()

for line in lines:
    if line[0] == '#' or line[0] == string.whitespace:
        continue
    params = line.split(',')
    if len(params) != 4:
        continue
    Timer(atof(params[2]),send_packet,[params[0],int(params[1]),int(params[3])]).start();
