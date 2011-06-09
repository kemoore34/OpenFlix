#! /usr/bin/python

from mininet.net import Mininet
from mininet.topo import Topo, Node, Edge, SingleSwitchTopo
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.util import run
# from mininet.util import run
from optparse import OptionParser
from threading import Thread
import time
import os
import re
import sys
import SocketServer
import socket
import signal

log = False

def _get_port_no( port_stat ):
    r = r'(\d+): rx pkts'
    m = re.search( r, port_stat)
    if m == None:
        print '*** Error: could not parse ping output: %s\n' % port_stat
        exit(0)
    return int(m.group(1))

def _get_rx_bytes( port_stat ):
    r = r'rx .* bytes=(\d+)'
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
            stats[port_no] = (rx_pkts, tx_pkts)
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

class HierarchicalTreeTopo(Topo):
    '''init

    @param c no. of core switches
    @param b no. of aggregation switches
    @param a no. of access switches
    '''
    global log

    def __init__(self, c=1, b=2, a=2):

        super(HierarchicalTreeTopo, self).__init__()
        self.log = log

        # define node ranges
        self.core = range(1, c+1) # c core switches
        self.aggregation = range(c+1, b+c+1) # b aggregation switches
        self.access = range(b+c+1, a+b+c+1) # a access switches
        self.servers = range(a+b+c+1, 3*a+b+c+1) # 2*a servers, 2 per access switch
        self.client = 3*a+b+c+1 # 1 client

        log_str = ''.join(['Starting HierarchicalTreeTopo with ', 
            '%d core, %d aggregate, %d access switches, ' % (c, b, a),
            'and %d servers\n' % len(self.servers)])
        if self.log: sys.stderr.write(log_str)

        # add switches
        for cc in self.core:
            self.add_node(cc, Node())
        for bb in self.aggregation:
            self.add_node(bb, Node())
        for aa in self.access:
            self.add_node(aa, Node())

        # add hosts
        self.add_node(self.client, Node(is_switch=False))
        for s in self.servers:
            self.add_node(s, Node(is_switch=False))

        # add links
        # client <-> core
        self.add_edge(self.client, self.core[0], Edge())
        # core <-> aggregation
        for cc in self.core:
            for bb in self.aggregation:
                self.add_edge(cc, bb, Edge())
        # aggregation <-> access
        for bb in self.aggregation:
            for aa in self.access:
                self.add_edge(bb, aa, Edge())
        # access <-> servers
        for aa in range(len(self.access)):
            sw = self.access[0] + aa
            s1 = self.servers[0] + 2*aa
            s2 = self.servers[0] + 2*aa + 1
            self.add_edge(sw, s1, Edge())
            self.add_edge(sw, s2, Edge())

        self.enable_all()

class HierarchicalTreeNet(object):
    global log

    # Default configuration is single core and 2 aggregates, and 4 access switches
    def __init__(self, c=1, b=2, a=2, ctrl_addr='127.0.0.1:6633'):
        self.log = log
        self.topo = HierarchicalTreeTopo(c, b, a)

        ctrl_args = ctrl_addr.split(':')
        ctrl_ip = ctrl_args[0]
        ctrl_port = int(ctrl_args[1]) if len(ctrl_args) > 1 else 6633
        
        if self.log: sys.stderr.write('Starting the Hierarchical network\n')

        self.net = Mininet(topo=self.topo, controller=lambda x:
                RemoteController(x, ctrl_ip, ctrl_port), 
                listenPort=6634, xterms=False, autoSetMacs=True)
        self.servers = [self.net.idToNode[s] for s in self.topo.servers]
        self.client = self.net.idToNode[self.topo.client]
        #self.serverIP = '10.0.0.100'
        #self.serverIPMask = 8
        self.net.start()
        # log server location
        self.log_server_loc('/tmp/server_loc.txt')
        self.log_topology('/tmp/topo.txt')

    def test(self):
        for s in self.servers:
            # set server IP
            #s.cmd('ifconfig', '%s:%d' % (s.intfs[0], 0), '%s/%d' % (self.serverIP, self.serverIPMask))
            # set static arp in servers for client IP
            #s.cmd('arp', '-s', self.client.IP(), self.client.MAC())
            # start client script
            if self.log: sys.stderr.write('Starting client %s\n' % s.name)

            #s.cmd('python', 'httpd.py', '80', '&')
            s.cmd('python', 'client.py', '%s.cfg'%s.name, '&')
            #TODO remove
            break

        os.system('rm -rf /tmp/time_log.txt')
        time.sleep(1)
        path_stats = []
        prev_stats = self.get_path_stats()
        if self.log: sys.stderr.write('Running test traffic...\n')
        output = self.client.cmd('python', 'server.py')
        print output

    def test_server_lb(self):
        print 'Testing server load-blancing...'
        p1 = True
        s = []
        srvrs = []
        tmp = []
        f = open('/tmp/time_log.txt', 'r')
        if self.log: sys.stderr.write('The client output...\n')
        for line in f:
            resp = line.strip().split()
            if self.log: sys.stderr.write(line)
            s.append(resp[2])
            tmp.append(resp[2])
            if resp[2].lower() == 'unknown':
                p1 = False
            if len(tmp) == len(self.servers):
                srvrs.append(tmp)
                tmp = []
        f.close()
        if self.log: sys.stderr.write('\n')

        if not p1:
            print 'FAIL! At least one request failed to get a response!'
            print 'Seen responses are from servers...'
            print s

        if len(set(srvrs[0])) != len(self.servers):
            print 'FAIL! All servers not used!'
            print 'Seen responses are from servers...'
            print s
            p1 = False

        for i in range(1,len(srvrs)):
            if srvrs[0] != srvrs[i]:
                print 'FAIL! Round robin scheme not used!'
                print 'Seen responses are from servers...'
                print s
                p1 = False
                break
        if p1:
            print 'PASS! - Passed all server load-balancing tests'
        return True

    def test_path_lb(self, path_stats):
        print 'Testing path load-blancing...'
        (p1, p2, p3) = (True, True, True)
        path = []
        for ps in path_stats:
            if self.log: sys.stderr.write('Path stats: %s\n' % str(ps))
            path_usage = []
            for (i,j) in ps:
                if (i < 1000) and (j < 1000):
                    path_usage.append(0)
                else:
                    path_usage.append(1)
            if self.log: sys.stderr.write('Path bitmask: %s\n' % str(path_usage))
            # test 1 - no. of paths used
            if(path_usage.count(1) != len(self.topo.access)):
                if self.log: sys.stderr.write('Test 1: Testing path usage...\n')
                print 'FAIL! - Test 1: No. of paths used'
                print 'Failed at : %s' % str(ps)
                p1 = False
            #test 2 - where the 1's occur
            relative_locs = [i%len(self.topo.aggregation) for i,j in
                    enumerate(path_usage) if j == 1]
            if len(set(relative_locs)) > 1:
                if self.log: sys.stderr.write('Test 2: Testing path consistency...\n')
                print 'FAIL! - Test 2: The same path not used'
                print 'Failed at : %s' % str(ps)
                p2 = False
            path.append(relative_locs[0])
        # test 3 - are you doing round robin?
        rr_paths = chunks(path, len(self.topo.aggregation))
        if self.log: sys.stderr.write('Test 3: Testing path round-robin...\n')
        if self.log: sys.stderr.write('Sequence of paths used: %s\n' % str(path))
        for i in range(1, len(rr_paths)):
            if rr_paths[0] != rr_paths[i]:
                print 'FAIL! - Test 3: Round-robin scheme not used'
                print 'Paths used: %s' % path
                p3 = False
                break
        if p1:
            print 'PASS! - Passed Test 1'
        if p2:
            print 'PASS! - Passed Test 2'
        if p3:
            print 'PASS! - Passed Test 3'
        
        return (p1 and p2 and p3)


    def get_path_stats(self):
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
        client_id = self.topo.client
        switch_id = self.topo.core[0]
        switch = self.net.idToNode[switch_id]
        log_str = '%s %s %d\n' % (self.client.MAC(), switch.defaultMAC,
                self.topo.port(client_id, switch_id)[1])
        if self.log: sys.stderr.write(log_str)
        if f is not None:
            f.write(log_str)
        else:
            print log_str,
        if self.log: sys.stderr.write('\n')

        # log server information
        #if self.log: sys.stderr.write('Server location:\n')
        if self.log: sys.stderr.write('Client location:\n')
        for aa in range(len(self.topo.access)):
            switch_id = self.topo.access[0] + aa
            s1_id = self.topo.servers[0] + 2*aa
            s2_id = self.topo.servers[0] + 2*aa + 1
            switch = self.net.idToNode[switch_id]
            s1 = self.net.idToNode[s1_id]
            s2 = self.net.idToNode[s2_id]
            log_str1 = '%s %s %d\n' % (s1.MAC(), switch.defaultMAC,
                    self.topo.port(s1_id, switch_id)[1])
            log_str2 = '%s %s %d\n' % (s2.MAC(), switch.defaultMAC,
                    self.topo.port(s2_id, switch_id)[1])
            if self.log: sys.stderr.write('%s%s' % (log_str1, log_str2))
            if f is not None:
                f.write('%s%s' % (log_str1, log_str2))
            else:
                print log_str1, log_str2,
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
        core_id = self.topo.core[0]
        s_core = self.net.idToNode[core_id]
        for agg_id in self.topo.aggregation:
            s_agg = self.net.idToNode[agg_id]
            p1, p2 = self.topo.port(core_id, agg_id)
            log_str = '%s %d %s %d\n' % (s_core.defaultMAC, p1,
                    s_agg.defaultMAC, p2)
            if f is not None:
                f.write(log_str)

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

class SingleServerNet(object):
    global log

    def __init__(self, ctrl_addr='127.0.0.1:6633'):
	self.log = log
        self.k = 2
        self.topo = SingleSwitchTopo(k=self.k)

	ctrl_args = ctrl_addr.split(':')
	ctrl_ip = ctrl_args[0]
	ctrl_port = int(ctrl_args[1]) if len(ctrl_args) > 1 else 6633
	
	if self.log: sys.stderr.write('Starting the Single-server network\n')

	self.net = Mininet(topo=self.topo, controller= lambda x:
		RemoteController(x, ctrl_ip, ctrl_port),
		listenPort=6634, xterms=False, autoSetMacs=True)
        self.servers = [self.net.idToNode[s] for s in range(2, self.k -1 + 2)]
        self.client = self.net.idToNode[1+self.k]
        #self.serverIP = '10.0.0.100'
        #self.serverIPMask = 8
        self.net.start()
        # log server location
        self.log_server_loc('/tmp/server_loc.txt')
	self.log_topology('/tmp/topo.txt')

    def test(self):
        for s in self.servers:
            s.cmd('python', 'client.py', s.IP()+':1234', '&')
        if self.log: sys.stderr.write('Starting client %s\n' % s.name)
        # set static arp in client for server IP
        #self.client.cmd('arp', '-s', self.serverIP, 'FF:FF:FF:FF:FF:FF')
        os.system('rm -rf /tmp/time_log.txt')
        time.sleep(1)
        if self.log: sys.stderr.write('Running test traffic...\n')
        
        output = self.client.cmd('python' ,'server.py', s.IP()+':1234', '2', '1', '50')

    def log_server_loc(self, filename=None):
        f = None
        if filename is not None:
            try:
                f = open(filename, 'w')
            except IOError:
                print 'Could not open file %s for writing' % filename
                pass

        # log client information
        if self.log: sys.stderr.write('Client location:\n')
        client_id = self.k + 1
        switch = self.net.idToNode[1]
        log_str = '%s %s %d\n' % (self.client.MAC(), switch.defaultMAC,
            self.topo.port(client_id, 1)[1])
        if self.log: sys.stderr.write(log_str)
        if f is not None:
            f.write(log_str)
        else:
            print log_str,
        if self.log: sys.stderr.write('\n')

        # log server information
        if self.log: sys.stderr.write('Server location:\n')
        for server_id in range(2, self.k -1 + 2):
            s = self.net.idToNode[server_id]
            switch = self.net.idToNode[1]
            log_str = '%s %s %d\n' % (s.MAC(), switch.defaultMAC, self.topo.port(server_id, 1)[1])
            if self.log: sys.stderr.write(log_str)
            if f is not None:
                f.write(log_str)
            else:
                print log_str,
        if f is not None:
            f.close()
        if self.log: sys.stderr.write('\n')


    def log_topology(self, filename=None):

        f = None
        if filename is not None:
            try:
                f = open(filename, 'w')
            except IOError:
                print 'Could not open file %s for writing' % filename
                pass
        switch = self.net.idToNode[1]
        if f is not None:
            f.write('%s\n'%switch.defaultMAC)
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
    for s in mn.servers:
        if log: sys.stderr.write('Killing web-server in server %s\n' %
                s.name)
        s.cmd('kill %python')
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
    o_str = "Topology type"
    parser.add_option("-o", "--topology", action="store", dest="topo", type="int",
	    default=1, help=o_str)
    (options, args) = parser.parse_args()

    # verbose output?
    log = options.verbose

    # networks to run
    if (options.topo < 1 or options.topo > 2):
        sys.stdout.write("Topology must be either 1 or 2")
        die()
    elif options.topo == 1: 
        mn = SingleServerNet(ctrl_addr=options.ctrl_addr)
    elif options.topo == 2:
        mn = HierarchicalTreeNet(ctrl_addr=options.ctrl_addr)

    sys.stdout.write('Now, RESTART the controller and hit ENTER when you are done:')
    l = sys.stdin.readline()
    if l.strip().lower() == 'q':
        die()

    if options.test:
        time.sleep(5)
        mn.test()
    else:
        CLI(mn.net)

    stop(mn)

    mn = None
    shutdown()
