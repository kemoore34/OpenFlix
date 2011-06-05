'''
Created on Jun 5, 2011

@author: jeongjin
'''
import sys
import socket
from threading import Timer
from string import atoi, atof

#udp send_packet function
def send_packet(id):
    UDP_IP = destination[id][0]
    UDP_PORT = atoi(destination[id][1])
    pcount = packet_count[id]
    
    while(pcount) :
        pcount = pcount - 1
        sock = socket.socket( socket.AF_INET, # Internet
                              socket.SOCK_DGRAM ) # UDP
        sock.sendto( `packet_count[id] - pcount`, (UDP_IP, UDP_PORT) )
        print UDP_IP + ':' + `UDP_PORT` + ":" + `packet_count[id] - pcount` + "th packet sent"

#config_path
config_path = ""
if len(sys.argv) > 1 :
    config_path = sys.argv[1] 
else :
    config_path = "Netflix_Server.cfg"

#config loading    
f = open(config_path,'r')
lines = f.readlines()
f.close()

id = 0;
destination = {}
packet_count = {}

#parse config file and schedule sending
for line in lines: 
    if line[0] == '#' or line[0] == '\n' :
        continue
    params = line.split(',')
    if len(params) != 4:
        continue 
    
    destination[id] = params[0:2]
    packet_count[id] = atoi(params[3]) 

    Timer(atof(params[2]),send_packet,[id]).start();
    id = id + 1

    
    
    
    
