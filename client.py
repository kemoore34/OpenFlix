#! /usr/bin/python

import socket, sys, time, os, re
from string import atoi
from optparse import OptionParser

MIN_REPORT_NUM = 100

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
        self.recv_total = 0
        self.throttle_count = 0
        self.rate = 0
        self.qos_notification_interval = 1 #seconds
        self.return_ip = ""
        self.return_port = 0
        self.loss_threshold = 1.0
        self.verbose = False
        self.loss_stat = []
        self.connection_start_time = 0
        self.connection_end_time = 0
        self.time_list = {}
        self.last_log_write_ts = 0
        self.ts_log_name = "/tmp/client_ts-%s-%s.log" % (name,port)
        self.ts_f = open(self.ts_log_name, "w")

    def dump_log(self, force = False):
        try:
            if ( force or len(self.time_list) > MIN_REPORT_NUM ):
                for k in sorted(self.time_list.keys()):
                    self.ts_f.write(`k` + " " + `self.time_list[k]` + "\n")
                self.last_log_write_ts = time.time()
                self.time_list.clear()
        except:
            self.ts_f.write(sys.exc_info()[0])
            self.ts_f.write(sys.exc_info()[1])


    def client_exit(self, rcount, pcount, th_count):
        try:
            self.sock.close()
        except:
            pass
        if self.connection_start_time: self.connection_end_time = time.time()

        for loss in self.loss_stat: 
            seq1, seq2 = loss
            if seq1 < seq2:
                self.f.write('Skipped Seq from %d to %d\n'%loss) 
            elif seq1 > seq2:
                self.f.write('Recovered out of order packet from %d to %d\n'%loss)
        self.f.write('Number of times throttled: %d\n'%th_count)
        self.f.write('Received: %d / %d packets\n'% (rcount, pcount))
        self.f.write('Start time: %f\n'%self.connection_start_time)
        self.f.write('End time: %f\n'%self.connection_end_time)
        self.f.write('Duration: %f\n'%(self.connection_end_time - self.connection_start_time))
        self.f.close()
        #self.dump_log(True)
        self.ts_f.close()
        print 'Number of time throttled: %d'%th_count
        print 'Received: %d / %d packets'%(rcount,pcount)
    
        sys.exit()
    
    def run(self):
        self.f.write('Starting client at %s:%d with timeout:%d\n'%(self.ip, self.port, self.timeout))
        cmdlines = os.popen("ifconfig -a")
        r = r'.*inet addr:([0-9.]*).*'
        for l in cmdlines.readlines():
            m = re.search(r, l)
            if (m != None):
                self.f.write('My IP address is %s'%m.group(1))
                break
            
        for i in range(3):
            try:
                self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM ) # UDP
                self.sock.settimeout(self.qos_notification_interval)
                self.sock.bind((ip,port))
                temp_sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
                temp_sock.setblocking(0)
                break
            except IOError as (errno, strerror):
                self.f.write('socket error\n')
                self.f.write(`errno`)
                self.f.write(strerror)
                cmdlines = os.popen("lsof -i :"+str(self.port))
                for l in cmdlines.readlines(): self.f.write(l+"\n")
            except:
                self.f.write('Unknown socket error\n')
                self.f.write(sys.exc_info()[0])
                self.f.write(sys.exc_info()[1])
                cmdlines = os.popen("lsof -i :"+str(self.port))
                for l in cmdlines.readlines(): self.f.write(l+"\n")
            time.sleep(0.5)
        
        last_qos_time = 0
        prev_seq = 0
        timeout_period = 0
        ploss_count = 0
        while True:
            try:
                data, addr = self.sock.recvfrom(10000) # buffer size is 2048 bytes
                if data == 0: 
                    self.f.write('Error: Nothing received on socket\n')
                    self.client_exit()
                data_s = data.strip()
                cur_time = time.time()
                self.time_list[cur_time] = data_s
                #self.dump_log()

                # Termination condition check
                if data_s == 'Finish':
                    self.client_exit(self.recv_total, self.num_packets, self.throttle_count)

                # Reset timeout whenever a packet is received
                timeout_period = 0
                #self.recv_per_interval += 1
                self.recv_total += 1

                # Initialization upon first packet
                if last_qos_time == 0 : 
                    last_qos_time = cur_time
                    self.connection_start_time = cur_time 

                '''    
                if (cur_time - last_qos_time) >= self.qos_notification_interval :
                    # Change the quliaty to low
                    if (self.rate - self.recv_per_interval) > self.loss_threshold * self.rate :
                        self.throttle_count += 1
                        temp_sock.sendto("low",(self.return_ip,self.return_port))
                        #print 'sending qos change req to '+self.return_ip+':'+`self.return_port`
                    # Reset qos counter 
                    self.recv_per_interval = 0
                    last_qos_time = cur_time
                '''
     
                # Parse packet content
                seq, self.num_packets, self.rate = map(int, data_s.split('/')[:3])
                url = data_s.split('/')[3].split(':')
                self.return_ip = url[0]
                self.return_port = atoi(url[1])
                
                # Log sequence skips
                if prev_seq < seq - 1:
                    self.loss_stat.append((prev_seq, seq))
                    ploss_count += (seq - prev_seq - 1)
                    prev_seq = seq
                elif prev_seq > seq - 1:
                    # Recover as much out of order packet as possible
                    self.loss_stat.append((prev_seq, seq))
                    ploss_count -= 1
                else:
                    prev_seq = seq

                # QOS processing
                if cur_time - last_qos_time >= self.qos_notification_interval :
                    if ploss_count > self.loss_threshold * self.rate :
                        self.throttle_count += 1
                        temp_sock.sendto("low",(self.return_ip, self.return_port))
                    # Reset QOS counter
                    ploss_count = 0
                    last_qos_time = cur_time
                     
            except socket.timeout:
                timeout_period += self.qos_notification_interval
                if timeout_period >= self.timeout:
                    self.client_exit(self.recv_total, self.num_packets, self.throttle_count)
                
# parse options
parser = OptionParser()
v_str = "Print verbose output to stderr"
parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
        default=False, help=v_str)
i_str = "IP:port of the controller, default 127.0.0.1:1234"
parser.add_option("-i", "--interface", dest="ctrl_addr", type="string",
        default='',
        help=i_str, metavar="LISTEN_ADDR")
q_str = "Quality of service threshold.  Change quality when packet loss exceeds the given value. Ex) 0.02 = 2% loss." 
parser.add_option("-q", "--quality", action="store", type="float", dest="quality",
        default=1.0, help=q_str)
to_str = "Timeout"
parser.add_option("-t", "--timeout", dest="timeout",
        default=10.0, type='float', help=to_str)
c_str = "QOS interval in seconds"
parser.add_option("-c", "--qosinterval", dest="interval",
        default=1.0, type='float', help=c_str)
(options, args) = parser.parse_args()

if not options.ctrl_addr: parser.error("Missing interface address"); die()

ip, port = options.ctrl_addr.split(':')
port = int(port)
name = ip

client = Client(name, ip, port, options.timeout)
client.loss_threshold = options.quality
client.qos_notification_interval = options.interval
client.verbose = options.verbose
client.run()
