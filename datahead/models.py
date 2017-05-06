#!/usr/bin/python
# Copyright 2017, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Models for Datahead application.
'''
import logging
log = logging.getLogger(__name__)


class Host(object):
    '''
    A data collection host.
    '''
    def __init__(self):
        address      = None
        name         = None
 
