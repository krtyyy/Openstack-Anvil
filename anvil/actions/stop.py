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

from anvil import colorizer
from anvil import log

from anvil.actions import base

from anvil.actions.base import PhaseFunctors

LOG = log.getLogger(__name__)


class StopAction(base.Action):

    @staticmethod
    def get_lookup_name():
        return 'running'

    @staticmethod
    def get_action_name():
        return 'stop'

    def _order_components(self, components):
        components = super(StopAction, self)._order_components(components)
        components.reverse()
        return components

    def _run(self, persona, component_order, instances):
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Stopping %s.', colorizer.quote(i.name)),
                run=lambda i: i.stop(),
                end=lambda i, result: LOG.info("Stopped %s items.", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "Stopped"
            )
        # Knock off and phase files that are connected to starting
        self._delete_phase_files(['start'])
