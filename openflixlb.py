# Stub Controller
# Your job is to turn this into a load-balancer

import logging

from nox.lib.core import *
import nox.lib.openflow as openflow
from nox.lib.packet.ethernet import ethernet
from nox.lib.packet.ipv4 import ipv4
from nox.lib.packet.tcp import tcp
from nox.lib.packet.packet_utils import mac_to_str, mac_to_int
from nox.lib.netinet.netinet import create_datapathid_from_host, create_ipaddr, create_eaddr
from time import time
from operator import itemgetter
import re
import socket
import sys

log = logging.getLogger('nox.netapps.loadbalancer.loadbalancer')
CACHE_TIMEOUT = 300

class Topology(object):

    def __init__(self, data):
        self.dps = []
        self.links = {}
        link_re = re.compile('(\S+)\s+(\d+)\s+(\S+)\s+(\d+)')
        # Read link information
        lines = data.splitlines()
        if not len(lines):
            return
        dpline = lines[0]
        for k in dpline.split():
            dp = create_datapathid_from_host(create_eaddr(k).hb_long())
            self.dps.append(dp)
        for line in lines[1:]:
            r = link_re.match(line)
            if r is not None:
                dp1 = create_datapathid_from_host(create_eaddr(r.group(1)).hb_long())
                port1 = int(r.group(2))
                dp2 = create_datapathid_from_host(create_eaddr(r.group(3)).hb_long())
                port2 = int(r.group(4))
                if dp1 not in self.dps:
                    self.dps.append[dp1]
                if dp2 not in self.dps:
                    self.dps.append[dp2]
                if dp1 not in self.links:
                    self.links[dp1] = {}
                if dp2 not in self.links:
                    self.links[dp2] = {}

                self.links[dp1][dp2] = (port1, port2)
                self.links[dp2][dp1] = (port2, port1)

    def get_datapaths(self):
        return self.dps

    def get_neighbors(self, dp):
        if dp not in self.links:
            return []
        return self.links[dp].keys()

    def get_outlinks(self, dpsrc, dpdst):
        if dpsrc not in self.links:
            return None
        if dpdst not in self.links[dpsrc]:
            return None
        return self.links[dpsrc][dpdst]

    def print_topology(self):
        dps = self.get_datapaths()
        print ' '.join([str(dp) for dp in dps])
        for dp in dps:
            nbrs = self.get_neighbors(dp)
            print '%s : %s' % (str(dp), ','.join([str(n) for n in nbrs]))

class ServerLoc(object):

    def __init__(self, data):
        self.clients = {}
        self.servers = {}

        loc_re = re.compile('(\S+)\s+(\S+)\s+(\d+)')
        lines = data.splitlines()
        for line in lines:
            if line.startswith('#Servers:'):
                configType = 'Servers'
                continue
            elif line.startswith('#Clients:'):
                configType = 'Clients'
                continue

            r = loc_re.match(line)
            if r is not None:
                host = create_eaddr(r.group(1))
                dpid = create_datapathid_from_host(create_eaddr(r.group(2)).hb_long())
                port = int(r.group(3))
                if configType == 'Servers':
                    self.servers[host] = (dpid, port)
                elif configType == 'Clients':
                    self.clients[host] = (dpid, port)

    def print_server_loc(self):
        print 'Servers'
        for server, (dpid, port) in self.servers.items():
            print '%s -> (%s, %d)' % (str(server), str(dpid), port)
        print 'Clients'
        for client, (dpid, port) in self.clients.items():
            print '%s -> (%s, %d)' % (str(client), str(dpid), port)

class loadbalancer(Component):


    def __init__(self, ctxt):
        Component.__init__(self, ctxt)

        HOST, PORT = "localhost", 9999
        buf = {'server':'', 'topo':''}
        for arg in buf:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            sock.send(arg)
            print 'Reading %s data from Socket' % arg
            while True:
                data = sock.recv(1024)
                buf[arg] += data
                if not len(data):
                    break
            sock.close()
        self.sloc = ServerLoc(buf['server'])
        self.topo = Topology(buf['topo'])
        self.flow_table = dict()
        self.update_topology()

        core_dpid = self.sloc.servers.values()[0][0]
        self.aggr_sw = self.topo.get_neighbors(core_dpid)
        self.next_sw_idx = 0
        
        self.aggr_sw_counter = dict()
        for sw in self.aggr_sw:
            self.aggr_sw_counter[sw] = 0

    # Get datapath between server and client that uses given aggregate dpid
    def get_path(self, server_mac, aggr_dpid, client_mac):
        
        if server_mac not in self.sloc.servers.keys():
            print 'Unknown server mac'
            return
        if client_mac not in self.sloc.clients.keys():
            print 'Unknown client mac'
            return
        
        # Find reverse dp from core
        core_dp_rev = self.sloc.servers[server_mac]
        # Get access dp
        access_dp = self.sloc.clients[client_mac]
        
        dps = []
        core_in_port = core_dp_rev[1]
        core_out_port = self.topo.get_outlinks(core_dp_rev[0], aggr_dpid)[0]
        core_dp = (core_dp_rev[0], core_in_port, core_out_port)
        dps.append(core_dp) 

        aggr_in_port = self.topo.get_outlinks(core_dp_rev[0], aggr_dpid)[1]
        aggr_out_port = self.topo.get_outlinks(aggr_dpid, access_dp[0])[0]
        aggr_dp = (aggr_dpid, aggr_in_port, aggr_out_port)
        dps.append(aggr_dp)

        access_in_port = self.topo.get_outlinks(aggr_dpid, access_dp[0])[1]
        access_out_port = access_dp[1]
        access_dp = (access_dp[0], access_in_port, access_out_port)
        dps.append(access_dp)

        return dps

    def update_topology(self):
        #build any local topology state here if you need to
        pass

    def remove_redistribute(self, dpid, inport, packet, buf, bufid):
        packet_src = convert_to_eaddr(packet.src)
        packet_dst = convert_to_eaddr(packet.dst)
    
        ip_packet = packet.find('ipv4')
        udp_packet = packet.find('udp')
        # Process only UDP packets
        if (udp_packet == None): return
        
        packet_srcport = udp_packet.srcport
        packet_dstport = udp_packet.dstport

        if (packet_src, packet_dst, packet_srcport, packet_dstport) not in self.flow_table: return

        old_entry = self.flow_table.pop((packet_src, packet_dst, packet_srcport, packet_dstport))
        aggr_dpid = old_entry[1][0]
        self.aggr_sw_counter[aggr_dpid] -= 1

        sorted_node = sorted(self.aggr_sw_counter.items(), key = itemgetter(1))
        max_node = sorted_node[-1]
        min_node = sorted_node[0]
        new_dps = None

        # Select a path to redistribute
        if max_node[1] - min_node[1] > 1:
            for packet_src, packet_dst, packet_srcport, packet_dstport in self.flow_table:
                dps = self.flow_table[(packet_src, packet_dst, packet_srcport, packet_dstport)]
                if dps[1][0] == max_node[0]:
                    new_dps = self.get_path(packet_src, min_node[0], packet_dst)
                    self.flow_table[(packet_src, packet_dst, packet_srcport, packet_dstport)] = dps
                    self.aggr_sw_counter[min_node[0]] += 1

                    flow = extract_flow(packet)
                    flow[core.NW_TOS] = ip_packet.tos
 
                    # Remove old flow rules
                    for dp in old_entry:
                        flow[core.IN_PORT] = dp[1]
                        self.delete_datapath_flow(dp[0].as_host(), flow) 
                        rev_flow = self.build_reverse_flow(flow)
                        rev_flow[core.IN_PORT] = dp[2]
                        self.delete_datapath_flow(dp[0].as_host(), rev_flow) 

                    # Install flow rules
                    for dp in new_dps:
                        flow[core.IN_PORT] = dp[1]
                        actions = [[openflow.OFPAT_OUTPUT, [0, dp[2]]]]
                        
                        # Install flow rule
                        self.install_datapath_flow(dp[0].as_host(), flow, CACHE_TIMEOUT,
                                                   openflow.OFP_FLOW_PERMANENT, actions,
                                                   None, openflow.OFP_DEFAULT_PRIORITY,
                                                   dp[1], None)
                        # Install reverse path
                        rev_flow = self.build_reverse_flow(flow)
                        rev_flow[core.IN_PORT] = dp[2]
                        rev_actions = [[openflow.OFPAT_OUTPUT, [0, dp[1]]]]
                        self.install_datapath_flow(dp[0].as_host(), rev_flow, CACHE_TIMEOUT,
                                                   openflow.OFP_FLOW_PERMANENT, rev_actions,
                                                   None, openflow.OFP_DEFAULT_PRIORITY,
                                                   dp[2], None)
 

    def forward_packet(self, dpid, inport, packet, buf, bufid):
        packet_src = convert_to_eaddr(packet.src)
        packet_dst = convert_to_eaddr(packet.dst)
    
        ip_packet = packet.find('ipv4')
        udp_packet = packet.find('udp')
        # Process only UDP packets
        if (udp_packet == None): return
        
        packet_srcport = udp_packet.srcport
        packet_dstport = udp_packet.dstport

        # Skip packets that came in the wrong way
        if packet_src in self.sloc.clients.keys():
            return

        if (packet_src, packet_dst, packet_srcport, packet_dstport) in self.flow_table:
            dps = self.flow_table[(packet_src, packet_dst, packet_srcport, packet_dstport)]
            dps = dps[:]
        elif self.sloc.servers[packet_src][0] == create_datapathid_from_host(dpid):
            #print packet.src, packet_srcport, packet.dst, packet_dstport, self.next_sw_idx
            #Find max/min load on the nodes then assign aggregate with the minimum load
            dps = self.get_path(packet_src, self.aggr_sw[self.next_sw_idx], packet_dst)
            self.flow_table[(packet_src, packet_dst, packet_srcport, packet_dstport)] = dps
            self.aggr_sw_counter[self.aggr_sw[self.next_sw_idx]] += 1
            sorted_node = sorted(self.aggr_sw_counter.items(), key = itemgetter(1))
            min_node = sorted_node[0]
 
            self.next_sw_idx = self.aggr_sw.index(min_node[0])
        else:
            print 'Packet can only initiate connection from end-points'
            return
        
        # Skip switches that has the flow installed already
        for dp in dps[:]:
            if dp[0] == create_datapathid_from_host(dpid): break
            else: dps.remove(dp)

        # Install flow rules
        for dp in dps:
            flow = extract_flow(packet)
            flow[core.NW_TOS] = ip_packet.tos
            actions = [[openflow.OFPAT_OUTPUT, [0, dp[2]]]]
            
            # Install flow rule and forward the packet
            if dp[0] == create_datapathid_from_host(dpid):
                flow[core.IN_PORT] = inport
                self.install_datapath_flow(dpid, flow, CACHE_TIMEOUT,
                                           openflow.OFP_FLOW_PERMANENT, actions,
                                           bufid, openflow.OFP_DEFAULT_PRIORITY,
                                           inport, buf)
            # Install rest of flow rules
            else: 
                flow[core.IN_PORT] = dp[1]
                self.install_datapath_flow(dp[0].as_host(), flow, CACHE_TIMEOUT,
                                           openflow.OFP_FLOW_PERMANENT, actions,
                                           None, openflow.OFP_DEFAULT_PRIORITY,
                                           dp[1], None)
            #Install reverse path
            rev_flow = self.build_reverse_flow(flow)
            rev_flow[core.IN_PORT] = dp[2]
            rev_actions = [[openflow.OFPAT_OUTPUT, [0, dp[1]]]]
            self.install_datapath_flow(dp[0].as_host(), rev_flow, CACHE_TIMEOUT,
                                       openflow.OFP_FLOW_PERMANENT, rev_actions,
                                       None, openflow.OFP_DEFAULT_PRIORITY,
                                       dp[2], None)


    def build_reverse_flow(self,flow):
        # make reverse flow data
        reverse_flow = {}
        reverse_flow[core.DL_SRC] = flow[core.DL_DST]
        reverse_flow[core.DL_DST] = flow[core.DL_SRC]

        reverse_flow[core.DL_VLAN] = flow[core.DL_VLAN]
        reverse_flow[core.DL_VLAN_PCP] = flow[core.DL_VLAN_PCP]

        reverse_flow[core.NW_SRC] = flow[core.NW_DST]
        reverse_flow[core.NW_DST] = flow[core.NW_SRC]

        reverse_flow[core.TP_SRC] = flow[core.TP_DST]
        reverse_flow[core.TP_DST] = flow[core.TP_SRC]

        reverse_flow[core.NW_TOS] = flow[core.NW_TOS]

        return reverse_flow

    def packet_in_callback(self, dpid, inport, reason, pkt_len, bufid, packet):
        """Packet-in handler""" 

        if not packet.parsed:
            log.msg('Ignoring incomplete packet',system='loadbalancer')
            
        # don't forward lldp packets    
        if packet.type == ethernet.LLDP_TYPE:
            return CONTINUE
        if packet.type == ethernet.ARP_TYPE:
            return CONTINUE
        # Check if this is IP packet
        if packet.type != ethernet.IP_TYPE:
            return CONTINUE

        ip_packet = packet.find('ipv4')
        if (ip_packet.tos == 4):
            self.remove_redistribute(dpid, inport, packet, packet.arr, bufid)
        else:
            self.forward_packet(dpid, inport, packet, packet.arr, bufid)

        return CONTINUE

    def install(self):
        self.register_for_packet_in(self.packet_in_callback)
    
    def getInterface(self):
        return str(loadbalancer)

def getFactory():
    class Factory:
        def instance(self, ctxt):
            return loadbalancer(ctxt)

    return Factory()
