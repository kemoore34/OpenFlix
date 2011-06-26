#!/usr/bin/python

import sys,time,socket
from threading import Thread
from string import atoi

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
        
        sleep_time = 1. / self.rate_
        sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sd.setblocking(0)
        #sd.connect((self.ip_,self.port_))
        
        sdr = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sdr.bind((self.selfip_,self.selfport_))
        sdr.setblocking(0)
        packet_len = 100
        sent_count = 1;
        while(sent_count <= self.pcount_):
            time.sleep(sleep_time)
            try:
                rdata = sdr.recv(1000)
                if rdata == 'low':
                    #self.rate_ = (int) (0.8 * self.rate_)
                    #sleep_time = 1. / self.rate_
                    packet_len = 50; 
                    #print "rate is decreased. new rate is" + str(self.rate_)
                    print "quality is decreased. new quality length is " + str(50)
            except:
                pass
            
            
            msg = str(sent_count)+'/'+str(self.pcount_) +'/'+str(self.rate_) +'/'+self.selfip_+":"+str(self.selfport_)
            sdata = ' '*(packet_len - len(msg)) + msg
            
            try:
                sd.sendto(sdata,(self.ip_,self.port_))
                print str(sent_count) + "th packet sent"
                sent_count = sent_count + 1
            except:
                print "packet dropped. exit."
                sys.exit()
            
        
if __name__ == '__main__':
    if (sys.argv[0].find("pydoc") == -1):
        if (len(sys.argv) < 2 or
            sys.argv[1] == "--help" or
            sys.argv[1] == "-h"):
                print(sys.argv[0]+" URL_SELF URL_TO [rate] [number of packets = 20]")
                print(sys.argv[0]+"     URL_SELF: ip_address:port.  Ex. 127.0.0.1:80.")
                print(sys.argv[0]+"     URL_TO: ip_address:port.  Ex. 127.0.0.1:80.")
                print(sys.argv[0]+"     rate: packets per second.  -1 sends at maximum rate.")
                sys.exit(1)
                
    uri_self = (sys.argv[1]).split(":")
    uri = (sys.argv[2]).split(":")
    rate = int(sys.argv[3])
    num_packets = int(sys.argv[4])
   
    rg = ReqGenerator(uri_self[0],atoi(uri_self[1]),uri[0],atoi(uri[1]),rate,num_packets)
    rg.start();
    
    
