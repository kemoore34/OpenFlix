#!/usr/bin/python

import math
import sys,time,socket
from threading import Thread
from string import atoi
from optparse import OptionParser

# Generate request
class ReqGenerator(Thread):
    def __init__(self, self_ip, self_port, ip, port, rate, total_packets):
        Thread.__init__(self)
        self.selfip_ = self_ip;
        self.selfport_ =self_port;
        self.ip_= ip;
        self.port_= port;
        self.rate_= rate;
        self.total_packets_= total_packets;
        self.max_packet_len = packet_max_size
        self.aimd_rtt = 0.01 #seconds
        self.log_name = '/tmp/server-%s-%s.log' % (self_ip, self_port)
        self.f = open(self.log_name, "w")
    
    def run(self):

        
        if self.rate_ < 0:
            sleep_time = 0
        if self.rate_ > 1e6:
            self.f.write('Rate too fast\n')
            return
        elif self.rate_ == 0:
            self.f.write('Rate cannot be 0\n')
            return
        else:
            sleep_time = 1.0 / self.rate_
        
        self.f.write('Initializing socket\n')
        # Socket to send packet to clients
        sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sd.setblocking(0)
        # Socket to listen for packet size change requests
        sdr = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sdr.bind((self.selfip_,self.selfport_))
        # Non-blocking socket receive
        sdr.setblocking(0)  
        packet_len = self.max_packet_len
        sent_count = 0;
        start_time = time.time()

        # Start sending packet
        self.f.write('Sending packets\n')
        while(sent_count < self.total_packets_):
            time.sleep(sleep_time)
            # Process QOS
            try:
                rdata = sdr.recv(10000)
                if rdata == 'low':
                    packet_len = packet_len / 2
            except:
                # Perform additional increament at every RTT
                if packet_len < self.max_packet_len and sent_count % math.ceil(self.aimd_rtt * self.rate_) == 0: 
                    packet_len += 1
            
            cur_time = time.time()
            expected_packet_count = (cur_time - start_time) * self.rate_

            # Sleep might delay packets. Send queued packets
            while expected_packet_count > sent_count and sent_count < self.total_packets_ :
                sent_count += 1
                msg = str(sent_count)+'/'+str(self.total_packets_) +'/'+str(self.rate_) +'/'+self.selfip_+":"+str(self.selfport_)
                sdata = msg + ' '*(packet_len - len(msg))
                
                try:
                    sd.sendto(sdata,(self.ip_,self.port_))
                except:
                    self.f.write('Exception while trying to send\n')
                    print 'Exception while trying to send'
                    pass
        # Notify connection termination
        end_time = cur_time
        try:
            sd.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 4)
            sd.sendto('Finish',(self.ip_,self.port_))
        except:
            self.f.write('Failed to send Finish packet\n')
            print "Failed to send Finish packet"
            
        self.f.write('Sent %i packets\n'%sent_count)
        self.f.write('Transmission duration: %f\n'%(end_time-start_time))
        self.f.close()
        print "Completed send. Transmission duration: %f" % (end_time - start_time)
        sys.exit()
        
packet_max_size = 1400 #bytes
if __name__ == '__main__':
    # parse options
    parser = OptionParser()
    i_str = "IP:port of the server listening address, default 127.0.0.1:1234"
    parser.add_option("-i", "--interface", dest="svr_addr", type="string",
            default='127.0.0.1:1234', help=i_str, metavar="LISTEN_ADDR")
    d_str = "IP:port of the destination client address"
    parser.add_option("-d", "--destination", dest="dest_addr", type="string",
            default=None, help=d_str, metavar="DEST_ADDR")
    r_str = "Rate. Packets per second. Default is 89 which is 1Mbps"
    parser.add_option("-r", "--rate", dest="rate", type="int",
            default=-1, help=r_str)
    n_str = "Number of packets to send."
    parser.add_option("-n", "--number", dest="num", type="int",
            default=None, help=n_str)
    rk_str = "Rate. mbps"
    parser.add_option("--mbps", dest="rate_mbps", type="float",
            default=0, help=rk_str)
    nt_str = "Duration."
    parser.add_option("--duration", dest="duration", type="float",
            default=0, help=nt_str)
    pkt_str = "Max packet size."
    parser.add_option("--packet_size", dest="packet_max_size", type="int",
            default=1400, help=pkt_str)
 
    (options, args) = parser.parse_args()
    
    if not options.svr_addr or not options.dest_addr or not options.rate:
        parser.error("Missing parameters")

    uri_self = options.svr_addr.split(':')
    uri = options.dest_addr.split(':')

    if options.rate_mbps:
        rate = int((options.rate_mbps * 1000 * 1000 / 8) / packet_max_size )
    else:
        rate = int(options.rate)
    if options.duration:
        num_packets = int(rate * options.duration)
    else:
        num_packets = int(options.num)

    rg = ReqGenerator(uri_self[0], atoi(uri_self[1]), uri[0], atoi(uri[1]), rate, num_packets)
    rg.start();
    
    
