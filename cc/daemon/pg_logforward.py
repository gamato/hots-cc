#! /usr/bin/env python

"""
UDP server to handle UDP stream sent by pg_logforward.
WWW: https://github.com/mpihlak/pg_logforward

This also serves as an example of how to extend daemons with plugins.
Plugins discovery, probing and loading is provided by CCDaemon class.

Plugins can be probed early (upon discovery) or late (upon loading).
This daemon and its plugins provide example implementation of both.
For early probing see methods find_plugins() and _probe_func() below.
For late probing see method probe() of PgLogForwardPlugin class.
"""

import sys
import time

import skytools

from cc.daemon.udp_listener import UdpListener
from cc.daemon.plugins.pg_logforward import PgLogForwardPlugin

# use fast implementation if available, otherwise fall back to reference one
try:
    import tnetstring as tnetstrings
    tnetstrings.parse = tnetstrings.pop
except ImportError:
    import cc.tnetstrings as tnetstrings

pg_elevels_itoa = {
    10: 'DEBUG5',
    11: 'DEBUG4',
    12: 'DEBUG3',
    13: 'DEBUG2',
    14: 'DEBUG1',
    15: 'LOG',
    16: 'COMMERROR',
    17: 'INFO',
    18: 'NOTICE',
    19: 'WARNING',
    20: 'ERROR',
    21: 'FATAL',
    22: 'PANIC',
    }
pg_elevels_atoi = dict ((v,k) for k,v in pg_elevels_itoa.iteritems())


class PgLogForward (UdpListener):
    """ UDP server to handle UDP stream sent by pg_logforward. """

    log = skytools.getLogger ('d:PgLogForward')

    def reload (self):
        super(PgLogForward, self).reload()

        self.log_format = self.cf.get ('log-format')
        assert self.log_format in ['netstr']
        self.log_parsing_errors = self.cf.getbool ('log-parsing-errors', False)

    def _probe_func (self, cls):
        """ Custom plugin probing function """
        if not issubclass (cls, PgLogForwardPlugin):
            self.log.debug ("plugin %s is not of supported type", cls.__name__)
            return False
        if self.log_format not in cls.LOG_FORMATS:
            self.log.debug ("plugin %s does not support %r formatted messages", cls.__name__, self.log_format)
            return False
        return True

    def init_plugins (self):
        """ Load suitable plugins and initialise them """
        self.load_plugins (log_fmt = self.log_format)
        for p in self.plugins:
            p.init (self.log_format)

    def parse_json (self, data):
        """ Parse JSON datagram sent by pg_logforward """
        raise NotImplementedError

    def parse_netstr (self, data):
        """ Parse netstrings datagram sent by pg_logforward """
        try:
            keys = [ "elevel", "sqlerrcode", "username", "database",
                    "remotehost", "funcname", "message", "detail",
                    "hint", "context", "debug_query_string" ]
            pos = 0
            res = {}
            while data:
                res[keys[pos]], data = tnetstrings.parse (data)
                pos += 1
            res['elevel'] = int(res['elevel'])
            res['elevel_text'] = pg_elevels_itoa[res['elevel']]
            res['sqlerrcode'] = int(res['sqlerrcode'])
            return res

        except Exception, e:
            if self.log_parsing_errors:
                self.log.warning ("netstr parsing error: %s", e)
                self.log.debug ("failed netstring: {%s} [%i] %r", keys[pos], len(data), data)
            return None

    def parse_syslog (self, data):
        """ Parse syslog datagram sent by pg_logforward """
        raise NotImplementedError

    def process (self, data):
        start = time.time()
        size = len(data)

        if self.log_format == "netstr":
            msg = self.parse_netstr (data)
        else:
            raise NotImplementedError

        if msg:
            for p in self.plugins:
                try:
                    p.process (msg)
                except Exception, e:
                    self.log.exception ("plugin %s crashed", p.__class__.__name__)
                    self.log.debug ("%s", e)

        # update stats
        taken = time.time() - start
        self.stat_inc ('pg_logforward.count')
        self.stat_inc ('pg_logforward.bytes', size)
        self.stat_inc ('pg_logforward.seconds', taken)

    def work (self):
        self.log.info ("Listening on %s for %s formatted messages", self.listen_addr, self.log_format)
        self.log.info ("Starting IOLoop")
        self.ioloop.start()
        return 1


if __name__ == '__main__':
    s = PgLogForward ('pg_logforward', sys.argv[1:])
    s.start()
