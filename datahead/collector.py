#!/usr/bin/python
# Copyright 2017, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Entry point for Datahead application. Starts ValueCollector to listen for
Observe notifications for temperature readings.

Usage:
   $. ./collector.py
'''
import logging
log = logging.getLogger(__name__)

import os, pwd, random, sys
from   threading import Timer
from   soscoap import ClientResponseCode
from   soscoap import CodeClass
from   soscoap import MessageType
from   soscoap import OptionType
from   soscoap import RequestCode
from   soscoap import ServerResponseCode
from   soscoap import SuccessResponseCode
from   soscoap.message import CoapMessage
from   soscoap.message import CoapOption
from   soscoap.client  import CoapClient
from   soscoap.server  import CoapServer
from   datahead.models import Host
        
def getInvariantName(host):
    '''Provides a short string to name a host, based on host attributes that don't
    change.
    
    :param Host host: 
    :return:
    '''
    tail = host.address.split(':')[-1]
    return 'mote-{0}'.format(tail)

class ValueCollector(object):
    '''
    Collects data from network hosts. Uses an soscoap.CoapServer to send and
    receive messages with hosts.
    '''
    def __init__(self, sourcePort):

        self._coapServer = CoapServer(port=sourcePort+1)
        self._coapServer.registerForResourceGet(self._getResource)
        self._coapServer.registerForResourcePost(self._postResource)

        self._sourcePort = sourcePort
        self._coapClient = None
        
        self._hosts = []
        self._timer = None

    def _getResource(self, resource):
        '''Sets the value in the provided resource, to satisfy a GET request.
        '''
        log.debug('GET resource path is {0}'.format(resource.path))
    
    def _postResource(self, resource):
        '''Records the value from the provided resource, from a POST request. 
        
        Assumes the CoAP server handles any raised exception.
        
        Resources:
        
        - /dh/lo : 'Hello' message to record a new host. Does not expect a
                   payload; just uses the host's IP address. Also registers to
                   observe /dh/tmp.
        '''
        log.debug('POST resource path is {0}'.format(resource.path))
        if resource.path == '/dh/lo':
            log.debug('/dh/lo: received from {0}'.format(resource.sourceAddress[0]))
            
            # Search for existing host record; create if none
            try:
                host = next(x for x in self._hosts if (x.address == resource.sourceAddress[0]))
            except StopIteration:
                host = None
            if not host:
                host = self._createHost(resource)
                if host:
                    self._hosts.append(host)
                    log.info('/dh/lo: Created host for {0}'.format(host.address))
                    resource.resultClass = CodeClass.Success
                    resource.resultCode  = SuccessResponseCode.Created
                    # Queue up Observe registration
                    Timer(2, self._startObserve, [resource.sourceAddress]).start()
                else:
                    log.error('/dh/lo: Host creation failed for {0}'.format(resource.sourceAddress[0]))
                    resource.resultClass = CodeClass.ServerError
                    resource.resultCode  = ServerResponseCode.InternalServerError
            else:
                log.info('/dh/lo: Found host {0}'.format(host.name))
                # Queue up Observe registration
                Timer(2, self._startObserve, [resource.sourceAddress]).start()

        else:
            log.warn('Unknown path: {0}'.format(resource.path))
            resource.resultClass = CodeClass.ClientError
            resource.resultCode  = ClientResponseCode.NotFound

    def _createHost(self, resource):
        '''Creates a host record for the mote described in the provided resource.
        
        :param resource: 
        :return: The created host
        :rtype: Host
        '''
        host = Host()
        host.address = resource.sourceAddress[0]
        host.name    = getInvariantName(host)    # requires address

        return host

    def _observeTemp(self, message):
        '''Reads observe notifications for /dh/tmp
        '''
        prefix   = '0' if message.codeDetail < 10 else ''

        msg = 'Response code: {0}.{1}{2}; value {3}'
        log.info(msg.format(message.codeClass, prefix, message.codeDetail,
                            message.typedPayload()))

    def _startObserve(self, hostAddrTuple):
        '''Sends Observe registration request to host.

        Expected to run in a thread, so catches and logs any exceptions.
        '''
        try:
            # create message
            hostTuple = (hostAddrTuple[0], hostAddrTuple[1])

            msg             = CoapMessage(hostTuple)
            msg.messageType = MessageType.NON
            msg.codeClass   = CodeClass.Request
            msg.codeDetail  = RequestCode.GET
            msg.messageId   = random.randint(0, 65535)
            msg.addOption( CoapOption(OptionType.UriPath, 'dh') )
            msg.addOption( CoapOption(OptionType.UriPath, 'tmp') )

            # register
            msg.addOption( CoapOption(OptionType.Observe, 0) )
            msg.tokenLength = 2
            msg.token       = bytearray(2)
            msg.token[0]    = random.randint(0, 255)
            msg.token[1]    = random.randint(0, 255)

            # create client
            if not self._coapClient:
                self._coapClient = CoapClient(sourcePort=self._sourcePort, dest=hostTuple)
                self._coapClient.registerForResponse(self._observeTemp)

            # send message
            log.debug('Sending query')
            self._coapClient.send(msg)
        except:
            log.exception('Catch-all handler for Observe registration thread')

    def start(self):
        '''Starts networking; returns when networking is stopped.'''
        self._coapServer.start()

    def close(self):
        '''Releases resources'''
        if self._coapClient:
            self._coapClient.close()


if __name__ == "__main__":
    logging.basicConfig(filename='datahead.log', level=logging.DEBUG, 
                        format='%(asctime)s %(module)s %(message)s')
    log.info('Initializing Datahead collector')

    formattedPath = '\n\t'.join(str(p) for p in sys.path)
    log.info('Running collector with sys.path:\n\t{0}'.format(formattedPath))

    collector  = None
    sourcePort = 5682
    try:
        collector = ValueCollector( sourcePort )
        print('Starting Datahead collector')
        collector.start()
    except KeyboardInterrupt:
        pass
    except:
        log.exception('Catch-all handler for Datahead server')
    finally:
        if collector:
            collector.close()
