#!/usr/bin/python

from BaseHTTPServer import HTTPServer
from CGIHTTPServer import CGIHTTPRequestHandler
import sys

class FastHandler(CGIHTTPRequestHandler):
    def address_string(self):
	return 'client'

print 'Starting HTTP server'

serveradresse = ("",int(sys.argv[1]))
server = HTTPServer(serveradresse, FastHandler)
server.serve_forever()
