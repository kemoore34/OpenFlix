#! /usr/bin/python

import socket, sys
import ConfigParser

#exit_function
class Client:
    def __init__(self, name, ip, port, timeout, packet_count):
        self.name = name
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.packet_count = packet_count
        self.log_name = '/tmp/client-%s.log' % name

    def client_exit(self, rcount,pcount):
        self.sock.close()
        print '%d / %d'%(rcount, pcount)
        sys.exit();
    
    def run(self):
        f = open(self.log_name, "w")
        f.write('Starting client at %s:%d with timeout:%d\n'%(self.ip, self.port, self.timeout))
        
        self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM ) # UDP
        self.sock.settimeout(timeout)
        self.sock.bind((ip,port))

        recv_count = 0

        f.write('Waiting for packet...\n')
        while True:
            try:
                data, addr = self.sock.recvfrom( 1024 ) # buffer size is 1024 bytes
            except socket.timeout:
                self.client_exit(recv_count, packet_count)
                
            recv_count += 1        
            print '.',
            if recv_count == packet_count:
                f.write('Received %d packets\n'% packet_count)
                f.close()
                self.client_exit(recv_count, packet_count)    

#config_path
config_path = ""
if len(sys.argv) > 1 :
    config_path = sys.argv[1] 
else :
    config_path = "Netflix_Client.cfg"

config = ConfigParser.RawConfigParser()
config.read(config_path)

name = config.get('Client', 'name')
ip = config.get('Client', 'ip')
port = config.getint('Client', 'port')
timeout = config.getint('Client', 'timeout')
packet_count = config.getint('Client', 'packet_count')

client = Client(name, ip, port, timeout, packet_count)
client.run()
