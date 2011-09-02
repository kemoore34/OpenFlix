#! /usr/bin/python

from mininet.net import Mininet
from mininet.topo import Topo, Node, Edge, SingleSwitchTopo
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.util import run
from mininet.util import run
from optparse import OptionParser
from threading import Thread
from threading import Timer
import time
import os
import re
import sys
import SocketServer
import socket
import signal
import random
import datetime

log = False

def _get_port_no( port_stat ):
    r = r'(\d+): rx pkts'
    m = re.search( r, port_stat)
    if m == None:
        print '*** Error: could not parse ping output: %s\n' % port_stat
        exit(0)
    return int(m.group(1))

def _get_rx_drops( port_stat ):
    r = r'rx .* drop=(\d+)'
    m = re.search( r, port_stat)
    if m == None:
        print '*** Error: could not parse port stats output: %s\n' % port_stat
        exit(0)
    return int(m.group(1))

def _get_rx_bytes( port_stat ):
    r = r'rx .* bytes=(\d+)'
    m = re.search( r, port_stat)
    if m == None:
        print '*** Error: could not parse port stats output: %s\n' % port_stat
        exit(0)
    return int(m.group(1))

def _get_tx_drops( port_stat ):
    r = r'tx .* drop=(\d+)'
    m = re.search( r, port_stat)
    if m == None:
        print '*** Error: could not parse port stats output: %s\n' % port_stat
        exit(0)
    return int(m.group(1))

def _get_tx_bytes( port_stat ):
    r = r'tx .* bytes=(\d+)'
    m = re.search( r, port_stat)
    if m == None:
        print '*** Error: could not parse port stats output: %s\n' % port_stat
        exit(0)
    return int(m.group(1))

def _parse_dpctl(dpctl_output ):
        '''Parse dpctl output and returns a list of 
        (port_no, rx_packets, tx_packets) tuples.'''
        port_stats = dpctl_output.split('port ')[1:]
        stats = {}
        for port_stat in port_stats:
            port_no = _get_port_no( port_stat )
            rx_pkts = _get_rx_bytes( port_stat )
            tx_pkts = _get_tx_bytes( port_stat )
            stats[port_no] = (rx_pkts, tx_pkts )
        return stats

def do_dpctl_ports(sw, listenPort=6634):
    '''Send a dpctl cmd and return a list of port stats.
    sw: the switch to run dpctl on.
    returns: a dict of port_no: (rx, tx) tuples, where
    port_no: openflow port number
    rx: packets received
    tx: packets sent'''
    # This should be provided by mininet/net.py, add it for 
    # now as a hack for CS244 testing/grading.
    if sw == None:
        print "dpctl needs a valid switch as an argument"
        return None
    else:
        result = sw.cmd( 'dpctl dump-ports tcp:localhost:%d' % listenPort )
        return _parse_dpctl(result)

def chunks(l, n):
    return [l[i:i+n] for i in range(0, len(l), n)]


class BandwidthMonitor:
    '''Monitor link bandwidth.
    '''
    def __init__(self, interval, func):
        os.system('rm -rf /tmp/bandwidth')
        os.system('rm -rf /tmp/drops')
        self.func = func
        self.interval = interval
        self.timer = Timer(self.interval, self.recordBandwidth)
        self.stats = []
        BandwidthMonitor.last_total_rx = 0
        
    def recordBandwidth(self):
        # Measure bandwidth at every 0.5 sec
        curTime = time.time()
        diff_time = curTime - self.timer.start_time
        # Adjust timer to sync with the interval
        offset = self.interval - diff_time
        last_total_rx = BandwidthMonitor.last_total_rx
        self.timer = Timer(self.interval - offset, self.recordBandwidth)
        self.timer.start_time = curTime
        self.timer.start()

        client_stats = self.func()
        self.stats.append((curTime - self.begin_time, client_stats))

    def start(self):
        self.begin_time = time.time()
        self.timer.start_time = time.time()
        self.timer.start()

    def cancel(self):
        self.timer.cancel()
        try:
            f = open('/tmp/bandwidth', 'a')
            for stats in self.stats:
                # Write timestamp
                f.write('%f'%stats[0])
                rate_sum = 0
                for stat in stats[1]:
                    # Write tx
                    f.write(', %f'%stat[1])
                    rate_sum += stat[1]

                f.write(', %f'%rate_sum)
                f.write('\n')
                
            f.close()
        except:
            pass
        

class LocationServer(Thread):
    '''Send topology and server/client information to the nox controller'''
    global log

    class LocServeHandler(SocketServer.BaseRequestHandler):
        # serve topology and server information
        def handle(self):
            req = self.request.recv(1024)
            fname = ''
            if req == 'server':
                fname = '/tmp/server_loc.txt'
            elif req == 'topo':
                fname = '/tmp/topo.txt'
            else:
                return
            try:
                f = open(fname, 'r')
                buf = ''
                for l in f:
                    buf += l
                f.close()
                self.request.send(buf)
            except:
                pass

    class ModTcpServer(SocketServer.TCPServer):
        allow_reuse_address = True

    def __init__(self):
        Thread.__init__(self)
        self.log = log
        self.start()

    def run(self):
        if self.log: sys.stderr.write('Starting TCP location server on %s:%d\n' % ('0.0.0.0', 9999))
        self.server = LocationServer.ModTcpServer(('0.0.0.0', 9999), LocationServer.LocServeHandler)
        self.server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.serve_forever()

    def stop(self):
        if self.log: sys.stderr.write('Stopping TCP location server\n')
        self.server.shutdown()


class HierarchicalTreeTopo(Topo):
    '''init

    @param c no. of core switches
    @param b no. of aggregation switches
    @param a no. of access switches
    '''
    global log

    def __init__(self, d=4, c=1, b=2, a=2):

        super(HierarchicalTreeTopo, self).__init__()
        self.log = log

        # define node ranges
        self.core = range(1, c+1) # c core switches
        self.aggregation = range(c+1, b+c+1) # b aggregation switches
        self.access = range(b+c+1, a+b+c+1) # a access switches
        self.clients = range(a+b+c+1, (d+1)*a+b+c+1) # d*a clients, d per access switch
        self.servers = range((d+1)*a+b+c+1, (d+1)*a+b+2*c+1) # c servers

        log_str = ''.join(['Starting HierarchicalTreeTopo with ', 
            '%d servers, %d core, %d aggregate, %d access switches, ' % (c, c, b, a),
            'and %d clients\n' % len(self.clients)])
        if self.log: sys.stderr.write(log_str)

        # add switches
        for cc in self.core:
            self.add_node(cc, Node())
        for bb in self.aggregation:
            self.add_node(bb, Node())
        for aa in self.access:
            self.add_node(aa, Node())

        # add hosts
        for s in self.servers:
            sNode = Node(is_switch=False)
            self.add_node(s, sNode)
        for cl in self.clients:
            self.add_node(cl, Node(is_switch=False))

        # add links
        # server <-> core
        for s in self.servers:
            self.add_edge(s, self.core[s-self.servers[0]], Edge())

        # core <-> aggregation
        for cc in self.core:
            for bb in self.aggregation:
                self.add_edge(cc, bb, Edge())
        # aggregation <-> access
        for bb in self.aggregation:
            for aa in self.access:
                self.add_edge(bb, aa, Edge())
        # access <-> clients
        for aa in range(len(self.access)):
            sw = self.access[0] + aa
            # Add client to each port on switch
            for dd in range(d):
                cc = self.clients[0] + d*aa + dd
                self.add_edge(sw, cc, Edge())

        self.enable_all()

class HierarchicalTreeNet(object):
    global log

    # Default configuration is single core and 2 aggregates, and 4 access switches
    def __init__(self, d=4, c=1, b=2, a=2, ctrl_addr='127.0.0.1:6633'):
        self.log = log
        self.topo = HierarchicalTreeTopo(d, c, b, a)

        ctrl_args = ctrl_addr.split(':')
        ctrl_ip = ctrl_args[0]
        ctrl_port = int(ctrl_args[1]) if len(ctrl_args) > 1 else 6633
        
        if self.log: sys.stderr.write('Starting the Hierarchical network\n')

        self.net = Mininet(topo=self.topo, controller=lambda x:
                RemoteController(x, ctrl_ip, ctrl_port), 
                listenPort=6634, xterms=False, autoSetMacs=True)

        self.clients = [self.net.idToNode[cl] for cl in self.topo.clients]
        self.clients_dict = {}
        for cl in self.topo.clients:
            node = self.net.idToNode[cl]
            self.clients_dict[node.IP()] = node

        self.servers = [self.net.idToNode[s] for s in self.topo.servers]
        self.servers_dict = {}
        for s in self.topo.servers:
            node = self.net.idToNode[s]
            self.servers_dict[node.IP()] = node

        self.net.start()
        # log server location
        self.log_server_loc('/tmp/server_loc.txt')
        self.log_topology('/tmp/topo.txt')

    # Deprecated
    # Test numConn connections
    def test(self, numConn=1):
        total_packets = 900000 
        send_rate = 850
        timeout = 10
        cl_count = 0
        for cl in self.clients:
            cl.cmd('python', 'client.py', '-i', cl.IP()+':1234', '-t', `timeout`, '-q', `0.02`, '&>singletest.output', '&')
            cl.cmd('arp', '-s', self.servers[0].IP(), self.servers[0].MAC())
            self.servers[0].cmd('arp', '-s', cl.IP(), cl.MAC())
            cl_count += 1
            if cl_count >= numConn: break

        os.system('rm -rf /tmp/time_log.txt')
        time.sleep(1)
        if self.log: sys.stderr.write('Running test traffic...\n')

        # Send packets 
        cl_count = 0
        server_port = 1234
        for cl in self.clients: 
            output = self.servers[0].cmd('python' ,'server.py', '-i', self.servers[0].IP()+':'+str(server_port), 
                                         '-d', cl.IP()+':1234', '-r', `send_rate`, '-n', `total_packets`, '&')
            server_port += 1
            cl_count += 1
            if cl_count >= numConn: break

        start_time = time.time()
        time.sleep(float(total_packets)/send_rate)

        # Print packet statistics for each client
        filelist = os.listdir('/tmp/')
        recvCount = 0
        totalCount = 0
        for filename in filelist:
            if filename.startswith('client-'):
                while True:
                    f = open('/tmp/'+filename, 'r')
                    lines = f.readlines()
                    f.close()
                    if len(lines):
                        lastline = lines.pop()
                        if lastline.startswith('Received'):
                            tokens = lastline.split()
                            recvCount += int(tokens[1])
                            totalCount += int(tokens[3])
                            break
                    else:
                        time.sleep(1)
        print 'Received ' + `recvCount` + ' / ' + `totalCount`
        print 'Experiment took ' + `(time.time()-start_time)` + 'secs.'


    # Generate random replay file and test it
    def randomtest(self, avgTransmit=10.0, avgWait=20.0, totalTime=200.0):
        filepath = '/tmp/random.replay'
        f = open(filepath, 'w')
        replay = list()
        count = 0
        port = 1234
        
        for cl in self.clients:
            curTime = 0
            port = 1234
            while(True):
                startTime = random.expovariate(1/avgWait) 
                txTime = random.expovariate(1/avgTransmit)

                # Generate traffic until total time
                if(curTime+startTime+txTime > totalTime): break
                else:
                    replay.append((curTime+startTime, cl.IP()+':'+str(port), curTime+startTime+txTime))
                    port += 1
                    curTime += startTime + txTime

        # Write replay to file sorted by timestamp
        replay.sort()
        count = 0
        port = 1234
        for startTime, dstIP, endTime in replay:
            srcIP = self.servers[count%len(self.servers)].IP()+':'+str(port+count)
            f.write("%f %s %s %f\n"%(startTime, srcIP, dstIP, endTime))
            count += 1
        f.close()
        #self.replay(filepath)

    # Replay a replay file
    def replay(self, filename, packet_rate=850, timeout=10, fast_monitor=False):
        terminate_time = 0.0
        curTime = 0.0
        graceTime = 10.0
        monitor_interval = 1
        if fast_monitor: 
            monitor_interval = 0.1

        if filename is not None:
            # Start bandwidth monitor
            #bm = BandwidthMonitor(monitor_interval, self.get_access_client_stats)
            #bm.start()
            
            try:
                f = open(filename, 'r')
                for l in f:
                    if l.startswith('#'): continue
                    send_time, src_addr, dst_addr, end_time = l.split()
                    if send_time < curTime:
                        print "Error: Send time later than the current time."
                        break
                    time.sleep(float(send_time) - curTime)
                    curTime = float(send_time)
                
                    '''
                    #TODO delete ipLog
                    ipLog = []
                    ipLog2 = []
                    ipLog3 = []
                    ipKeys = self.clients_dict.keys()
                    for cl in self.clients: 
                        cl_ip = cl.IP()
                        ipLog.append(cl_ip)
                        ipLog.append(id(cl))
                        ipLog.append(cl)
                        ipLog2.append(ipKeys[self.clients.index(cl)])
                        ipLog2.append(id(self.clients_dict[ipKeys[self.clients.index(cl)]]))
                        ipLog2.append(self.clients_dict[ipKeys[self.clients.index(cl)]])
                        ipLog3.append(cl_ip)
                        ipLog3.append(id(cl))
                        ipLog3.append(cl)
                        if cl_ip == dst_addr.split(':')[0]:
                            break
                        cl = None
                    for s in self.servers:
                        s_ip = s.IP()
                        if s_ip == src_addr.split(':')[0]:                    
                            break
                        s = None

                    if cl == None:
                        print 'iplog'
                        print ipLog
                        print 'iplog2'
                        print ipLog2
                        print 'iplog3'
                        print ipLog3
                        print 'cur list'
                        for cl in self.clients:
                            print cl.IP()
                            print id(cl)
                            print cl
                        die()
                    '''
                    #TODO good code
                    cl = self.clients_dict[dst_addr.split(':')[0]]
                    s = self.servers_dict[src_addr.split(':')[0]]
                    #'''
                    total_packets = int(packet_rate * (float(end_time)-float(curTime)))

                    if float(end_time) > terminate_time: 
                        terminate_time = float(end_time)

                    cl.cmd('arp', '-s', s.IP(), s.MAC())
                    cl.cmd('python', 'client.py', '-i', dst_addr, '-t', `timeout`, '-q', `0.05`, '&')
                    s.cmd('arp', '-s', cl.IP(), cl.MAC())
                    s.cmd('python' ,'server.py', '-i', src_addr, '-d', dst_addr, '-r', `packet_rate`, 
                            '-n', `total_packets`, '&')
                    print `curTime`, src_addr, '->', dst_addr, 'packets:', total_packets
                f.close()
                # Wait until all packets are sent
                wait_time = terminate_time-curTime
                time.sleep(wait_time)
                total_tx = self.get_total_rx()
                avg_throughput = total_tx / terminate_time

                # Print packet statistics for each client
                filelist = os.listdir('/tmp/')
                recvCount = 0
                totalCount = 0
                throttleCount = 0
                for filename in filelist:
                    if filename.startswith('client-'):
                        while True:
                            f = open('/tmp/'+filename, 'r')
                            lines = f.readlines()
                            f.close()
                            if len(lines) > 2:
                                for line in lines:
                                    if line.find('Received:') >= 0:
                                        r = r'.*: (\d+) \/ (\d+).*'
                                        m = re.search(r, line)
                                        recvCount += int(m.group(1))
                                        totalCount += int(m.group(2))
                                    elif line.find('throttled:') >= 0:
                                        r = r'.*: (\d+)'
                                        m = re.search( r, line)
                                        throttleCount += int(m.group(1))
                                break
                            else:
                                time.sleep(1) 
                # Calculate throughput

                f = open('/tmp/result', 'w')
                f.write('Total: '+`recvCount`+' / '+`totalCount` + '\n')
                f.write('Avg Throughput: '+`avg_throughput/1000` +'KBps\n')
                f.write('Total throttled: '+`throttleCount`+'\n')
                f.close()
                print 'Total '+`recvCount`+' / '+`totalCount`
                print 'Total TX: ' + `total_tx`
                print 'Avg Throughput: '+`avg_throughput/1000` +'KBps'

                # Cleanup
                #bm.cancel()
    
            except IOError:
                print 'Could not open replay file %s' % filename
                pass
        else:
            die()

    def get_access_path_stats(self):
        listenPort = 6634
        stats = []
        for ac in sorted(self.topo.access):
            ac_sw = self.net.idToNode[ac]
            all_stats = do_dpctl_ports(ac_sw, listenPort + ac - 1)
            for ag in sorted(self.topo.aggregation):
                ag_sw = self.net.idToNode[ag]
                port = self.topo.port(ac, ag)[0]
                stats.append(all_stats[port])
        return stats

    def get_access_client_stats(self):
        listenPort = 6634
        stats = []
        for aa in range(len(self.topo.access)):
            ac_sw_id = self.topo.access[0] + aa
            ac_sw = self.net.idToNode[ac_sw_id]
            all_stats = do_dpctl_ports(ac_sw, listenPort + ac_sw_id - 1)

            d = len(self.topo.clients) / len(self.topo.access)
            # Print client attached to each port
            for dd in range(d):
                cc_id = self.topo.clients[0] + d*aa + dd
                cc = self.net.idToNode[cc_id]
                port = self.topo.port(ac_sw_id, cc_id)[0]
                stats.append(all_stats[port])
        return stats 

    def get_total_rx(self):
        total_rx = 0
        for path_stat in self.get_access_path_stats():
           total_rx += path_stat[0]
        return total_rx

    def log_server_loc(self, filename=None):
        f = None
        if filename is not None:
            try:
                f = open(filename, 'w')
            except IOError:
                print 'Could not open file %s for writing' % filename
                pass

        # log client information
        #if self.log: sys.stderr.write('Client location:\n')
        if self.log: sys.stderr.write('Server location:\n')
        log_str = '#Servers: Do not delete this line\n'
        if f is not None:
            f.write(log_str)
        for s_idx in range(len(self.topo.servers)):
            server_id = self.topo.servers[s_idx]
            switch_id = self.topo.core[s_idx]
            switch = self.net.idToNode[switch_id]
            log_str = '%s %s %d\n' % (self.servers[s_idx].MAC(), switch.defaultMAC, self.topo.port(server_id, switch_id)[1])
            if self.log: sys.stderr.write(log_str)
            if f is not None:
                f.write(log_str)
            else:
                print log_str,

        if self.log: sys.stderr.write('\n')

        # log server information
        #if self.log: sys.stderr.write('Server location:\n')
        if self.log: sys.stderr.write('Client location:\n')
        log_str = '#Clients: Do not delete this line\n'
        if f is not None:
            f.write(log_str)
        for aa in range(len(self.topo.access)):
            switch_id = self.topo.access[0] + aa
            switch = self.net.idToNode[switch_id]

            d = len(self.topo.clients) / len(self.topo.access)
            # Print client attached to each port
            for dd in range(d):
                cc_id = self.topo.clients[0] + d*aa + dd
                cc = self.net.idToNode[cc_id]
                log_str = '%s %s %d\n' % (cc.MAC(), switch.defaultMAC,
                        self.topo.port(cc_id, switch_id)[1])
                if self.log: sys.stderr.write(log_str)
                if f is not None:
                    f.write(log_str)
                else:
                    print log_str,
        if f is not None:
            f.close()

    def log_topology(self, filename=None):
        f = None
        if filename is not None:
            try:
                f = open(filename, 'w')
            except IOError:
                print 'Could not open file %s for writing' % filename
                pass
        # log all dpids
        log_str = ' '.join([self.net.idToNode[sid].defaultMAC for sid in
            self.topo.core+self.topo.aggregation+self.topo.access])
        if f is not None:
            f.write(log_str+'\n')
        # log core -> aggregation
        for core_id in self.topo.core:
            s_core = self.net.idToNode[core_id]
            for agg_id in self.topo.aggregation:
                s_agg = self.net.idToNode[agg_id]
                p1, p2 = self.topo.port(core_id, agg_id)
                log_str = '%s %d %s %d\n' % (s_core.defaultMAC, p1,
                        s_agg.defaultMAC, p2)
                if f is not None:
                    f.write(log_str)

        for agg_id in self.topo.aggregation:
            s_agg = self.net.idToNode[agg_id]
            # log aggregation -> access
            for acc_id in self.topo.access:
                s_acc = self.net.idToNode[acc_id]
                p1, p2 = self.topo.port(agg_id, acc_id)
                log_str = '%s %d %s %d\n' % (s_agg.defaultMAC, p1,
                        s_acc.defaultMAC, p2)
                if f is not None:
                    f.write(log_str)
        if f is not None:
            f.close()

def start(mn, num_requests):
    global log
    os.system('rm -rf /tmp/time_log.txt')
    time.sleep(1)
    if log: sys.stderr.write('Starting request generation...\n')
    output = mn.client.cmd('./client/client.py',
            'http://%s/cgi-bin/noop.py'%mn.serverIP, '2', '1', str(num_requests))
    print output
    os.system('cat /tmp/time_log.txt')

def stop(mn):
    global log
    if log: sys.stderr.write('Stopping the network...\n')
    for c in mn.clients:
        if log: sys.stderr.write('Killing web-server in server %s\n' %
                c.name)
        c.cmd('kill %python')
    if log: sys.stderr.write('Killing NOX, if any running\n')
    run('killall nox_core lt-nox_core')
    mn.net.stop()

mn = None
loc_server = None

def shutdown():
    global log, mn, loc_server
    if mn:
        stop(mn)
    if loc_server:
        loc_server.stop()
        loc_server.join()
    if log:
        sys.stderr.write('Bye, Bye!\n')

def die(signum=None, frame=None):
    try:
        shutdown()
    finally:
        # If we're dying because of a signal, exit with an error code.
        if signum:
            sys.exit(1)
        sys.exit(0)

def quit(mn=None, loc_server=None):
    global log
    if mn:
        stop(mn)
    if loc_server:
        loc_server.stop()
        loc_server.join()
    if log: sys.stderr.write('Bye, Bye!\n')

if __name__ == '__main__':
    signal.signal(signal.SIGINT, die)

    # parse options
    parser = OptionParser()
    v_str = "Print verbose output to stderr"
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
            default=False, help=v_str)
    i_str = "IP:port of the controller, default 127.0.0.1:6633"
    parser.add_option("-i", "--interface", dest="ctrl_addr", type="string",
            default='127.0.0.1:6633',
            help=i_str, metavar="CONTROLLER_ADDR")
    t_str = "Test your solution"
    parser.add_option("-t", "--test", action="store_true", dest="test",
            default=False, help=t_str)
    r_str = "Replay traffic"
    parser.add_option("-p", "--replay", type="string", dest="replay",
            default=None, help=r_str)
    rand_str = "Genrate random traffic"
    parser.add_option("-r", "--random", action="store_true", dest="random",
            default=False, help=rand_str)
    o_str = "Topology type"
    parser.add_option("-o", "--topology", action="store", dest="topo", type="int",
            default=1, help=o_str)
    fm_str = "Fast Monitor"
    parser.add_option("", "--fastmonitor", action="store_true", dest="fast_monitor",
            default=False, help=fm_str)
    (options, args) = parser.parse_args()

    # verbose output?
    log = options.verbose

    # Delete existing logs
    os.system('rm -rf /tmp/*')

    # location server
    loc_server = LocationServer()
    time.sleep(2)

    # networks to run
    if (options.topo < 1 or options.topo > 3):
        sys.stdout.write("Topology must be either 1 or 2")
        die()
    elif options.topo == 1: 
        mn = HierarchicalTreeNet(d=4, c=1, b=4, a=4, ctrl_addr=options.ctrl_addr)
    elif options.topo == 2:
        mn = HierarchicalTreeNet(d=4, c=4, b=4, a=4, ctrl_addr=options.ctrl_addr)
    elif options.topo == 3:
        mn = HierarchicalTreeNet(d=2, c=1, b=1, a=1, ctrl_addr=options.ctrl_addr)
    else:
        sys.stdout.write('No topology given')
        die()

    sys.stdout.write('Now, RESTART the controller and hit ENTER when you are done:')
    l = sys.stdin.readline()
    if l.strip().lower() == 'q':
        die()

    if options.replay:
        time.sleep(5)
        mn.replay(options.replay, fast_monitor = options.fast_monitor)
    elif options.random:
        time.sleep(5)
        mn.randomtest()
    elif options.test:
        time.sleep(5)
        mn.test(numConn=1)
    else:
        CLI(mn.net)

    stop(mn)

    mn = None
    shutdown()
