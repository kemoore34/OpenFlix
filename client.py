#! /usr/bin/python

import socket, sys, time
from string import atoi
from optparse import OptionParser

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
        self.rate = 0
        self.return_ip = ""
        self.return_port = 0
        self.qc = False
        self.verbose = False

    def client_exit(self, rcount,pcount):
        self.sock.close()
        print '%d / %d'%(rcount, pcount)

        self.f.write('Received %d / %d packets\n'% (rcount, pcount))
        self.f.close()
        sys.exit()
    
    def run(self):
        self.f.write('Starting client at %s:%d with timeout:%d\n'%(self.ip, self.port, self.timeout))
        print 'Starting client at %s:%d with timeout:%d'%(self.ip, self.port, self.timeout)
        
        self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM ) # UDP
        self.sock.settimeout(timeout)
        self.sock.bind((ip,port))

        self.f.write('Waiting for packet...\n')
        
        last_time = 0
        while True:
            try:
                data, addr = self.sock.recvfrom( 1024 ) # buffer size is 1024 bytes
                
                self.rate_recv_count +=1
                self.recv_count += 1

                if self.qc:
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
                
                url = seq_total.split('/')[3].split(':')
                self.return_ip = url[0]
                self.return_port = atoi(url[1])
                
                # Terminate client
                if seq == self.num_packets:
                    self.client_exit(self.recv_count, self.num_packets)
                     
            except socket.timeout:
                self.client_exit(self.recv_count, self.num_packets)
                
# parse options
parser = OptionParser()
v_str = "Print verbose output to stderr"
parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
        default=False, help=v_str)
i_str = "IP:port of the controller, default 127.0.0.1:1234"
parser.add_option("-i", "--interface", dest="ctrl_addr", type="string",
        default='127.0.0.1:1234',
        help=i_str, metavar="LISTEN_ADDR")
q_str = "Enable Quality Control"
parser.add_option("-q", "--quality", action="store_true", dest="quality",
        default=False, help=q_str)
(options, args) = parser.parse_args()

ip, port = options.ctrl_addr.split(':')
port = int(port)

name = ip
timeout = 30

client = Client(name, ip, port, timeout)
client.qc = options.quality
client.verbose = options.verbose
client.run()
