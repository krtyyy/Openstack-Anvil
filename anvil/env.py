# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os

from anvil import log as logging


LOG = logging.getLogger(__name__)


def get():
    return dict(os.environ)


def set(key, value):
    # This is really screwy, python is really odd in this area
    # See: from http://docs.python.org/library/os.html
    # Calling putenv() directly does not change os.environ, so it's better to modify os.environ.
    if key is not None:
        # LOG.audit("Setting environment key %r to value %r" % (str(key), str(value)))
        os.environ[str(key)] = str(value)


def get_key(key, default_value=None):
    if not key:
        return default_value
    key = str(key)
    # LOG.debug("Looking up environment variable %r" % (key))
    value = get().get(key)
    if value is None:
        # LOG.debug("Could not find anything in environment variable %r" % (key))
        value = default_value
    else:
        pass
        # LOG.audit("Found %r in environment variable %r" % (value, key))
    return value
