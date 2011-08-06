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
        self.log_name = '/tmp/client-%s-%s.log' % (name,port)
        self.f = open(self.log_name, "w")
        self.num_packets = 0
        self.recv_count_total = 0
        self.recv_count_per_sec = 0
        self.rate = 0
        self.return_ip = ""
        self.return_port = 0
        self.packet_loss_threshold = 1.0
        self.verbose = False
        self.timeout_count = 0

    def client_exit(self, rcount,pcount, th_count=0):
        self.sock.close()
        print 'Number of times throttled: %d'%th_count
        print 'Received %d / %d packets'%(rcount, pcount)

        self.f.write('Number of times throttled: %d\n'%th_count)
        self.f.write('Received %d / %d packets\n'% (rcount, pcount))
        self.f.close()
        sys.exit()
    
    def run(self):
        self.f.write('Starting client at %s:%d with timeout:%d\n'%(self.ip, self.port, self.timeout))
        print 'Starting client at %s:%d with timeout:%d'%(self.ip, self.port, self.timeout)
        
        self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM ) # UDP
        self.sock.settimeout(1)
        self.sock.bind((ip,port))

        self.f.write('Waiting for packet...\n')
        
        throttle_count = 0
        last_qos_time = 0
        while True:
            try:
                data, addr = self.sock.recvfrom(2048) # buffer size is 2048 bytes
                # Reset timeout whenever a packet is received
                self.timeout_count = 0
                self.recv_count_per_sec += 1
                self.recv_count_total += 1

                if last_qos_time == 0 : last_qos_time = time.time()
                else : 
                    cur_time = time.time()

                    if (cur_time - last_qos_time) >= 1 :
                        # Change the quliaty to low
                        if (self.rate - self.recv_count_per_sec) > self.packet_loss_threshold * self.rate :
                            throttle_count += 0
                            temp_sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
                            temp_sock.setblocking(0)
                            temp_sock.sendto("low",(self.return_ip,self.return_port))
                            temp_sock.close()
                        # Reset counter 
                        self.recv_count_per_sec = 0
                        last_qos_time = cur_time
                            
                data_s = data.strip()
                seq, self.num_packets, self.rate = map(int, data_s.split('/')[:3])
                
                url = data_s.split('/')[3].split(':')
                self.return_ip = url[0]
                self.return_port = atoi(url[1])
                
                # Terminate client
                if seq == self.num_packets:
                    self.client_exit(self.recv_count_total, self.num_packets, throttle_count)
                     
            except socket.timeout:
                self.timeout_count += 1
                if self.timeout_count >= self.timeout:
                    self.client_exit(self.recv_count_total, self.num_packets, throttle_count)
                
# parse options
parser = OptionParser()
v_str = "Print verbose output to stderr"
parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
        default=False, help=v_str)
i_str = "IP:port of the controller, default 127.0.0.1:1234"
parser.add_option("-i", "--interface", dest="ctrl_addr", type="string",
        default='',
        help=i_str, metavar="LISTEN_ADDR")
q_str = "Quality of service threshold.  Change quality when packet loss rate exceeds the given rate." 
parser.add_option("-q", "--quality", action="store", type="float", dest="quality",
        default=1.0, help=q_str)
to_str = "Timeout"
parser.add_option("-t", "--timeout", dest="timeout",
        default=10.0, type='float', help=to_str)
(options, args) = parser.parse_args()

if not options.ctrl_addr: parser.error("Missing interface address"); die()

ip, port = options.ctrl_addr.split(':')
port = int(port)
name = ip

client = Client(name, ip, port, options.timeout)
client.packet_loss_threshold = options.quality
client.verbose = options.verbose
client.run()
