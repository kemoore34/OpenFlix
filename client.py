#! /usr/bin/python

import socket, sys

#exit_function
class Client:
    def __init__(self, name, ip, port, timeout):
        self.name = name
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.log_name = '/tmp/client-%s.log' % name
        self.f = open(self.log_name, "w")
        self.num_packets = 0
        self.recv_count = 0

    def client_exit(self, rcount,pcount):
        self.sock.close()
        print '%d / %d'%(rcount, pcount)

        self.f.write('Received %d / %d packets\n'% (rcount, pcount))
        self.f.close()
        sys.exit();
    
    def run(self):
        self.f.write('Starting client at %s:%d with timeout:%d\n'%(self.ip, self.port, self.timeout))
        print 'Starting client at %s:%d with timeout:%d'%(self.ip, self.port, self.timeout)
        
        self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM ) # UDP
        self.sock.settimeout(timeout)
        self.sock.bind((ip,port))

        self.f.write('Waiting for packet...\n')
        
        while True:
            try:
                data, addr = self.sock.recvfrom( 1024 ) # buffer size is 1024 bytes
            except socket.timeout:
                self.client_exit(self.recv_count, self.num_packets)
                
            self.recv_count += 1        
            seq_total = data.strip()
            seq, self.num_packets = map(int, seq_total.split('/'))
            
            # Terminate client
            if seq == self.num_packets:
                self.client_exit(self.recv_count, self.num_packets)    

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

client = Client(name, ip, port, timeout)
client.run()
