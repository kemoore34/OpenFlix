#!/usr/bin/python
import socket
import sys, time, signal
from threading import Thread
import struct
import select
import random
import re
from urlparse import urlsplit

class ReqGenerator(Thread):
    def __init__(self, rate, uri_list, req_dict, lock, sock_dict, time_dict,  max_conn, my_poll, req_per_thread):
        Thread.__init__(self)

        self.rate_ = rate
        self.req_list_ = uri_list
        self.lock_ = lock
        self.sock_dict_ = sock_dict
        self.time_dict_ = time_dict
        self.max_conn_ = max_conn
        self.my_poll_ = my_poll
        self.req_dict_ = req_dict
        self.total_req_ = req_per_thread
        
        self.setDaemon(True) # detached thread
        self.start()
        
    # connect socket and prepare request
    def send_http(self, sd, url):
        addr = self.get_address(url)
        if addr is not None:
            req = "GET " + self.get_resource(url) + " HTTP/1.1" + "\r\n"
            req += "Host: " + addr[0] + ":" + str(addr[1]) + "\r\n"
            req += "Connection: close" + "\r\n"
            #req += "Cookie: time=%f\r\n" % time.time()
            req += "\r\n"
            self.req_dict_[sd.fileno()] = req
            #print req
            try:
                sd.connect(addr)
            except:
                pass

    # parses url to get hostname and port
    def get_address(self, url):
        u = urlsplit(url)
        r = u.netloc.split(":")
        if len(r) < 2:
            return (r[0], 80)
        return (r[0], int(r[1]))

    def get_resource(self, url):
        u = urlsplit(url)
        if u.path != '':
            return u.path
        return '/'

    def run(self):
        self.lock_.acquire()
        try:
            next_t = 1. / self.rate_[0] 
        except:
            pass
        old_t = time.time() - random.random() * next_t
        self.lock_.release()
        
        
        # main loop
        for i in range(self.total_req_):
            # make sure we never sleep too long, in case we change the Rate from something very low
            if next_t > 1.:
                next_t = 1.
            if next_t < 0:
                next_t = 0

            # sleep until needed
            time.sleep(next_t);
            
            self.lock_.acquire()
            try:
                # check for 0 request rate
                if self.rate_[0] <= 1e-5:
                    self.lock_.release()
                    continue

                if( time.time() - old_t - (1. / self.rate_[0]) < -0.01 ):
                    self.lock_.release()
                    continue


                # check if new request needs/can to be sent
                if (len(self.req_list_) > 0) and (len(self.sock_dict_) < self.max_conn_):

                    sd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                    # non blocking sockets
                    sd.setblocking(0)

                    # keep connection start time for logging purposes
                    self.time_dict_[sd.fileno()] = time.time()

                    # send next http request
                    uri = self.req_list_[0]
                    try:
                        print '.',
                        sys.stdout.flush()
                        self.send_http(sd, uri)
                    except:
                        print(sys.exc_info()[0])
                        print(sys.exc_info()[1])
                        self.lock_.release()
                        continue

                    # register socket for the poll
                    self.my_poll_.register(sd, select.POLLIN | select.POLLOUT)
                    
                    # keep a reference to the socket, otherwise it gets destroyed, because poll.register() only
                    # remembers the file descriptor
                    self.sock_dict_[sd.fileno()] = sd

                # update timeout for the next poll (wake up to send a new request on time)
                next_t = 1. / self.rate_[0]
                old_t = time.time()
                self.lock_.release()
            # if something goes wrong, ignore it and try to recover
            except:
                #print(sys.exc_info()[2])
                next_t = 1. / self.rate_[0]
                self.lock_.release()
                old_t = time.time()
