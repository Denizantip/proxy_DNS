import asyncio
import configparser
import struct
import sys

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass


class Datagram:
    def __init__(self, endpoint, black_list):
        self.endpoint = endpoint
        self.remotes = {}
        self.black_list = black_list

    def connection_made(self, transport):  # от клиента
        self.transport = transport

    def datagram_received(self, data, addr):
        self.id = struct.unpack(byteorder() + '2s', data[:2])[0]
        self.data = data[2:].decode()
        self.addr = addr
        self.DATA = data
        if get_domain_name(data) in self.black_list:
            self.transport.sendto(self.id + b'Restricted Domain name', self.addr)
            return
        if self.data in self.remotes.keys():
            self.transport.sendto(self.id + self.remotes[self.data], self.addr)
            return
        loop = asyncio.get_event_loop()
        listen = loop.create_datagram_endpoint(lambda: Remote(self), remote_addr=self.endpoint)
        asyncio.ensure_future(listen)

    def connection_lost(self, exc):
        self.transport.close()


class Remote:
    def __init__(self, datagram):
        self.datagram = datagram

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.datagram.DATA)

    def datagram_received(self, rec_data, _):
        self.datagram.remotes[self.datagram.data] = rec_data[2:]
        self.datagram.transport.sendto(self.datagram.id + rec_data[2:], self.datagram.addr)
        self.transport.close()

    def connection_lost(self, exc):
        self.transport.close()


def byteorder():
    return "<" if sys.byteorder == "little" else ">"


def get_config():
    defaults = {"addr": "127.0.0.1", "port": "53", "DNS_addres": "8.8.8.8", "DNS_port": "53", "Black_list": ""}
    config = configparser.ConfigParser()
    if config.read('config.ini'):
        defaults = dict(config.items('default'))
        return defaults
    with open('config.ini', 'w') as f:
        config.add_section('default')
        config['default'] = defaults
        config.write(f)
    return defaults


def get_domain_name(data):
    start = 12
    quantity = data[start]
    result = ''
    while quantity != 0:
        result += data[start + 1: start + quantity + 1].decode() + '.'
        start += quantity + 1
        quantity = data[start]
    return result[:-1]


def main(addr, port, dns_addres, dns_port, black_list):
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    print("Starting UDP server")
    coroutine = loop.create_datagram_endpoint(lambda: Datagram((dns_addres, int(dns_port)), black_list),
                                              local_addr=(addr, int(port)))
    transport, _ = loop.run_until_complete(coroutine)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        transport.close()
        loop.close()


if __name__ == '__main__':
    main(**get_config())
