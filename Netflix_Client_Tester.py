#! /usr/bin/python

import sys
import socket
import ConfigParser
from threading import Timer

from string import atoi

#exit_function
def client_exit(rcount,pcount,sock):
    sock.close()
    print '%d / %d'%(rcount, pcount)
    sys.exit();
    
#config_path
config_path = ""
if len(sys.argv) > 1 :
    config_path = sys.argv[1] 
else :
    config_path = "Netflix_Client.cfg"

config = ConfigParser.RawConfigParser()
config.read(config_path)

ip = config.get('Client', 'ip')
port = config.getint('Client', 'port')
timeout = config.getint('Client', 'timeout')
packet_count = config.getint('Client', 'packet_count')
print 'Starting client at %s:%d with timeout:%d'%(ip, port, timeout)

sock = socket.socket( socket.AF_INET, # Internet
                      socket.SOCK_DGRAM ) # UDP
sock.settimeout(timeout)
sock.bind((ip,port))

recv_count = 0

print 'Waiting for packet...'
while True:
    try:
        data, addr = sock.recvfrom( 1024 ) # buffer size is 1024 bytes
    except socket.timeout:
        client_exit(recv_count, packet_count, sock)
        
    recv_count += 1        
    print '.',
    if recv_count == packet_count :
	print 'Received %d packets'% packet_count
        client_exit(recv_count, packet_count, sock)    
    #print "received message:", data

