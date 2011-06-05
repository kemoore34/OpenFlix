'''
Created on Jun 5, 2011

@author: jeongjin
'''
import sys
import socket
from threading import Timer

from string import atoi

#exit_function
def client_exit(rcount,pcount,sock):
    sock.close()
    print `rcount` + '/' + `pcount`
    sys.exit();
    
#config_path
config_path = ""
if len(sys.argv) > 1 :
    config_path = sys.argv[1] 
else :
    config_path = "Netflix_Client.cfg"

#config loading    
f = open(config_path,'r')
lines = f.readlines()
f.close()

UDP_IP = "127.0.0.1"
UDP_PORT = 0;
packet_count = 0;
time_out = 0;

for line in lines: 
    if line[0] == '#' or line[0] == '\n' :
        continue
    params = line.split(',')
    if len(params) != 3:
        print "Config Format Error"
        sys.exit()
    
    UDP_PORT = atoi(params[0])
    packet_count =atoi(params[1])
    time_out = atoi(params[2])

sock = socket.socket( socket.AF_INET, # Internet
                      socket.SOCK_DGRAM ) # UDP
sock.settimeout(time_out)
sock.bind( (UDP_IP,UDP_PORT) )

recv_count = 0

while True:
    try:
        data, addr = sock.recvfrom( 1024 ) # buffer size is 1024 bytes
    except socket.timeout:
        client_exit(recv_count, packet_count, sock)
        
    recv_count = recv_count + 1        
    if recv_count == packet_count :
        client_exit(recv_count, packet_count, sock)    
    #print "received message:", data

