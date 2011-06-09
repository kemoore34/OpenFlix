#! /usr/bin/python

import socket, sys

#exit_function
class Client:
    def __init__(self, name, ip, port, timeout, packet_count):
        self.name = name
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.packet_count = packet_count
        self.log_name = '/tmp/client-%s.log' % name
        self.f = open(self.log_name, "w")

    def client_exit(self, rcount,pcount):
        self.sock.close()
        print '%d / %d'%(rcount, pcount)

        self.f.write('Received %d packets\n'% rcount)
        self.f.close()
        sys.exit();
    
    def run(self):
        self.f.write('Starting client at %s:%d with timeout:%d\n'%(self.ip, self.port, self.timeout))
        print 'Starting client at %s:%d with timeout:%d'%(self.ip, self.port, self.timeout)
        
        self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM ) # UDP
        self.sock.settimeout(timeout)
        self.sock.bind((ip,port))

        recv_count = 0

        self.f.write('Waiting for packet...\n')
        while True:
            try:
                data, addr = self.sock.recvfrom( 1024 ) # buffer size is 1024 bytes
            except socket.timeout:
                self.client_exit(recv_count, packet_count)
                
            recv_count += 1        
            print '.',
            if recv_count == packet_count:
                self.client_exit(recv_count, packet_count)    

#config_path
config_path = ""
if len(sys.argv) > 1 :
    ip, port = sys.argv[1].split(':')
    port = int(port)
else :
    ip = '127.0.0.1'
    port = 80

name = ip
timeout = 30
packet_count = 2000

client = Client(name, ip, port, timeout, packet_count)
client.run()
