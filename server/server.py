#!/usr/bin/python

import socket, sys
import time
from server_gen import ReqGenerator
import threading
import select
import random

RESP_TIME_AVG_N = 5
MIN_REPORT_NUM = 0

class Server:
    def __init__(self, uri, rate, max_conn, num_req_threads, req_per_thread, log_name):
        self.num_req_threads_ = num_req_threads
        self.ctrl_lock_ = threading.Lock()
        self.rate_ = [rate,]
        self.req_list_ = [uri,]
        self.sock_dict_ = {}
        self.time_dict_ = {}
        self.name_dict_ = {}
        self.servermac_dict_ = {}
        self.head_dict_ = {}
        self.req_dict_ = {}
        self.size_dict_ = {}
        self.time_list_ = {} 
        self.resp_times_ = []
        self.servermacs_ = []
        self.last_log_write_ts_ = time.time()
        self.my_poll_ = select.poll()
        self.log_file_name_ = log_name
        self.slaves = []
        
        # make sure we don't divide by zero
        if self.rate_[0] < 1e-6:
            self.rate_[0] = 1e-6

        for i in range(num_req_threads):
            self.slaves.append(ReqGenerator(self.rate_, self.req_list_, self.req_dict_, self.ctrl_lock_, self.sock_dict_, self.time_dict_, max_conn, self.my_poll_, req_per_thread))
            time.sleep(random.random())

    # dump time_log into file (call while holding ctrl_lock_)
    def dump_log(self, force = False):
        try:
            if( (len(self.time_list_)>0) and (force or ( (len(self.time_list_)>MIN_REPORT_NUM) and ((time.time() - self.last_log_write_ts_ > report_interval))) ) ): # write log every few seconds
                f = open(self.log_file_name_, "a")
		#print 'dump_log'
                for t in sorted(self.time_list_.keys()):
                    f.write(str(self.time_list_[t])+"\n")
                self.last_log_write_ts_ = time.time()
                del self.servermacs_[:]
		self.time_list_.clear()
                del self.resp_times_[:]
        except:
            print sys.exc_info()[0]
            print sys.exc_info()[1]

    def fin_sock(self, sd):
        #print 'FIN_Sock'
        self.my_poll_.unregister(sd)

        if sd not in self.name_dict_:
            self.name_dict_[sd] = "Unknown"
        if sd not in self.servermac_dict_:
            self.servermac_dict_[sd] = "Unknown"
        if sd not in self.size_dict_:
            self.size_dict_[sd] = 0
        try:
            t = time.time() - self.time_dict_[sd];
            self.time_list_[self.time_dict_[sd]] = str(self.time_dict_[sd]) + '\t' + self.name_dict_[sd] + "\t" + self.servermac_dict_[sd] + "\t" + str(t)
            self.resp_times_.append(t)                 
            mac_list = self.servermac_dict_[sd].split(':')
            mac_val = 0
            #print mac_list
            try:
                for j in range(len(mac_list)):
                    mac_val = mac_val + pow(256, len(mac_list)-j-1) * int(mac_list[j], 16);
                self.servermacs_.append(mac_val)
            except:
                pass
        except:
            print sys.exc_info()[0]
            print sys.exc_info()[1]

        self.sock_dict_[sd].close()
        del self.sock_dict_[sd]
        
        if sd in self.time_dict_:
            del self.time_dict_[sd]
        if sd in self.name_dict_:
            del self.name_dict_[sd]
        if sd in self.servermac_dict_:
            del self.servermac_dict_[sd]
        if sd in self.size_dict_:
            del self.size_dict_[sd]

    # main function that polls all fds
    def run(self):

        # main loop
        while True:
            time.sleep(0.001)
            self.ctrl_lock_.acquire()

            try:
                # log connection times to a file
                self.dump_log()
                
                # poll all registered sockets
                res = self.my_poll_.poll(0)
                
                # process all events that occured
                for r in res:
                    # other side closed the connection
                    if ( r[1] & (select.POLLHUP | select.POLLNVAL | select.POLLERR) ) != 0:
                        self.fin_sock(r[0])
                        continue
                    
                    if (r[1] & select.POLLIN) != 0:
                        # on linux closed socket is detected by read returning 0 -- no POLLHUP :( 
                        #print 'Received POLLIN'
                        rd_buf = self.sock_dict_[r[0]].recv(10000)
                        #print rd_buf
                        if len(rd_buf) == 0:
                            self.fin_sock(r[0])
                        elif len(rd_buf) > 0:
                        #if r[0] not in self.name_dict_:
                            if r[0] not in self.head_dict_:
                                self.head_dict_[r[0]] = ""
                            self.head_dict_[r[0]] += rd_buf
                            end_i = self.head_dict_[r[0]].find("\r\n\r\n")
                            #if  end_i != -1:                                                          
                                #self.head_dict_[r[0]] = self.head_dict_[r[0]][:end_i+2] 
                            srv_name = "Unknown"
                            mac_name = "Unknown"
                            content_len = "0"
                            try:
                                buf = self.head_dict_[r[0]]
                                sname_loc = buf.find("Server-name:")
                                if sname_loc >= 0:
                                    srv_name = buf[buf.find("Server-name:")+len("Server-name:"):].lstrip()
                                    srv_name = srv_name[:srv_name.find(";\r\n")].rstrip()
                                mname_loc = buf.find("Server-mac:")
                                if mname_loc >= 0:
                                    mac_name = buf[buf.find("Server-mac:")+len("Server-mac:"):].lstrip()
                                    mac_name = mac_name[:mac_name.find(";\r\n")].rstrip()
                                cloc = buf.find("Content-length:")
                                if cloc >= 0:
                                    content_len = buf[buf.find("Content-length:")+len("Content-length:"):].lstrip()
                                    content_len = content_len[:content_len.find("\r\n")].rstrip()
                                    if(content_len.find(";") != -1):
                                        content_len = content_len[:content_len.find(";")].rstrip()
                            except:
                                pass
                            if r[0] not in self.name_dict_ or srv_name != 'Unknown':
                                self.name_dict_[r[0]] = srv_name 
                            if r[0] not in self.servermac_dict_ or mac_name != 'Unknown':
                                self.servermac_dict_[r[0]] = mac_name
                            #self.size_dict_[r[0]] = int(content_len) - (len(rd_buf) - end_i + 2) 
                            del self.head_dict_[r[0]]
                            #if(self.size_dict_[r[0]] <= 0):
                                #self.fin_sock(r[0])
                            #print '******************', self.name_dict_[r[0]], self.servermac_dict_[r[0]], '********************'
                        #else:
                            #self.size_dict_[r[0]] = self.size_dict_[r[0]] - len(rd_buf) 
                            #if(self.size_dict_[r[0]] <= 0):
                                #self.fin_sock(r[0])
                                
                    if (r[1] & select.POLLOUT) != 0:
                        self.time_dict_[r[0]] = time.time()
                        self.sock_dict_[r[0]].send(self.req_dict_[r[0]])
                        self.my_poll_.unregister(r[0])
                        self.my_poll_.register(r[0], select.POLLIN)

                # see if all threads have finished
                stop = True
                for s in self.slaves:
                    stop &= not s.is_alive()
                    if not stop:
                        break

                # see if sockets have been taken care of
                if stop:
                    stop &= (len(self.sock_dict_) == 0)

                self.ctrl_lock_.release()

                # time to finish up
                if stop:
                    self.dump_log(True)
                    print
                    break

            # catch ctrl+c
            except KeyboardInterrupt:
                self.ctrl_lock_.release()
                quit()

            # if something goes wrong, ignore it and try to recover
            except:
                print(sys.exc_info()[0])
                print(sys.exc_info()[1])
                self.ctrl_lock_.release()
            
def main(uri, rate, max_conns, num_th, req_per_thread, log_name):
    server = Server(uri, rate, max_conns, num_th, req_per_thread, log_name); 
    server.run()

if __name__ == '__main__':
    max_conns = 1
    num_th = 1
    req_per_thread = 1
    log_name = "/tmp/time_log.txt"
    report_interval = .1
    if (sys.argv[0].find("pydoc") == -1):
        if (len(sys.argv) < 2 or
            sys.argv[1] == "--help" or
            sys.argv[1] == "-h"):
                print(sys.argv[0]+" URL [rate] [req threads = 1] [req per thread = 1]")
                sys.exit(1)

    uri = sys.argv[1]
    rate = float(sys.argv[2])
    num_th = int(sys.argv[3])
    req_per_thread = int(sys.argv[4])
   
    main(uri, rate, max_conns, num_th, req_per_thread, log_name)
