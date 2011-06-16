#! /usr/bin/python

import socket, sys, time
from string import atoi
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
        self.rate_recv_count = 0
        self.rate = 0;
        self.return_ip = ""
        self.return_port = 0;

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
        
        last_time = 0;
        while True:
            try:
                data, addr = self.sock.recvfrom( 1024 ) # buffer size is 1024 bytes
                
                self.rate_recv_count +=1
                self.recv_count += 1
                
                if last_time==0 :
                    last_time = time.time()
                else :
                    new_time = time.time()
                    
                    if (new_time - last_time) >= 1 :
                        if self.rate_recv_count < (0.8*self.rate) :
                            #print str(self.rate_recv_count) + " < " +str(0.8*self.rate)
                            temp_sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
                            temp_sock.setblocking(0)
                            temp_sock.sendto("low",(self.return_ip,self.return_port))
                            temp_sock.close()
                        self.rate_recv_count = 0
                        last_time = new_time
                        
                seq_total = data.strip()
                #print seq_total
                seq, self.num_packets, self.rate = map(int, seq_total.split('/')[:3])
                
                url = seq_total.split('/')[3].split(':');
                self.return_ip = url[0];
                self.return_port = atoi(url[1]);
                
                # Terminate client
                if seq == self.num_packets:
                    self.client_exit(self.recv_count, self.num_packets)
                     
            except socket.timeout:
                self.client_exit(self.recv_count, self.num_packets)
                
                

#config_path
config_path = ""
if len(sys.argv) > 1 :
    ip, port = sys.argv[1].split(':')
    port = int(port)
else :
    ip = '127.0.0.1'
    port = 1234 

name = ip
timeout = 30

client = Client(name, ip, port, timeout)
client.run()
