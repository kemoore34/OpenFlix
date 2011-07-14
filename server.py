#!/usr/bin/python

import sys,time,socket
from threading import Thread
from string import atoi
from optparse import OptionParser

class ReqGenerator(Thread):
    def __init__(self, self_ip, self_port, ip, port, rate, pcount):
        Thread.__init__(self)
        
        self.selfip_ = self_ip;
        self.selfport_ =self_port;
        
        self.ip_= ip;
        self.port_= port;
        self.rate_= rate;
        self.pcount_= pcount;
    
    def run(self):
        
        if self.rate_ < 0:
            sleep_time = 0
        elif self.rate_ == 0:
            return
        else:
            sleep_time = 1. / self.rate_
        
        # Socket to send packet to clients
        sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sd.setblocking(0)
        
        # Socket to listen for packet size change requests
        sdr = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sdr.bind((self.selfip_,self.selfport_))
        # Non-blocking socket receive
        sdr.setblocking(0)  
        packet_len = 1400
        sent_count = 1;
        while(sent_count <= self.pcount_):
            time.sleep(sleep_time)
            try:
                rdata = sdr.recv(2048)
                if rdata == 'low':
                    packet_len = 512; 
                    #print "rate is decreased. new rate is" + str(self.rate_)
                    print "quality is decreased. new quality length is " + str(packet_len)
            except:
                pass
            
            
            msg = str(sent_count)+'/'+str(self.pcount_) +'/'+str(self.rate_) +'/'+self.selfip_+":"+str(self.selfport_)
            sdata = msg + ' '*(packet_len - len(msg))
            
            try:
                sd.sendto(sdata,(self.ip_,self.port_))
                sent_count = sent_count + 1
            except:
                print "packet dropped. exit."
                break
        # Notify connection termination
        try:
            sd.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 4)
            sd.sendto('Finish',(self.ip_,self.port_))
        except:
            print "Finish packet failed to send"
            
        sys.exit()
            
        
if __name__ == '__main__':
    # parse options
    parser = OptionParser()
    i_str = "IP:port of the server listening address, default 127.0.0.1:1234"
    parser.add_option("-i", "--interface", dest="svr_addr", type="string",
            default='127.0.0.1:1234', help=i_str, metavar="LISTEN_ADDR")
    d_str = "IP:port of the destination client address"
    parser.add_option("-d", "--destination", dest="dest_addr", type="string",
            default=None, help=d_str, metavar="DEST_ADDR")
    r_str = "Rate. Packets sent per second. Do not set this option to send at maximum speed"
    parser.add_option("-r", "--rate", dest="rate", type="int",
            default=-1, help=r_str)
    n_str = "Number of packets to send."
    parser.add_option("-n", "--number", dest="num", type="int",
            default=None, help=n_str)
    (options, args) = parser.parse_args()

    uri_self = options.svr_addr.split(':')
    uri = options.dest_addr.split(':')
               
    rate = int(options.rate)
    num_packets = int(options.num)
   
    rg = ReqGenerator(uri_self[0],atoi(uri_self[1]),uri[0],atoi(uri[1]),rate,num_packets)
    rg.start();
    
    
