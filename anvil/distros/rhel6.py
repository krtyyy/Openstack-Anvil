# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 New Dream Network, LLC (DreamHost) All Rights Reserved.
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

"""Platform-specific logic for RedHat Enterprise Linux v6 components.
"""

import re

from anvil import colorizer
from anvil import log as logging
from anvil import shell as sh
from anvil import utils

from anvil.components import db
from anvil.components import horizon
from anvil.components import nova
from anvil.components import rabbit

from anvil.packaging import yum

from anvil.helpers import nova as nhelper

LOG = logging.getLogger(__name__)

# See: http://wiki.libvirt.org/page/SSHPolicyKitSetup
# FIXME: take from distro config??
LIBVIRT_POLICY_FN = "/etc/polkit-1/localauthority/50-local.d/50-libvirt-access.pkla"
LIBVIRT_POLICY_CONTENTS = """
[libvirt Management Access]
Identity={idents}
Action=org.libvirt.unix.manage
ResultAny=yes
ResultInactive=yes
ResultActive=yes
"""
DEF_IDENT = 'unix-group:libvirtd'


class DBInstaller(db.DBInstaller):

    def _configure_db_confs(self):
        LOG.info("Fixing up %s mysql configs.", colorizer.quote(self.distro.name))
        fc = sh.load_file('/etc/my.cnf')
        lines = fc.splitlines()
        new_lines = list()
        for line in lines:
            if line.startswith('skip-grant-tables'):
                line = '#' + line
            new_lines.append(line)
        fc = utils.joinlinesep(*new_lines)
        with sh.Rooted(True):
            sh.write_file('/etc/my.cnf', fc)


class HorizonInstaller(horizon.HorizonInstaller):

    def _config_fix_wsgi(self):
        # This is recorded so it gets cleaned up during uninstall
        self.tracewriter.file_touched("/etc/httpd/conf.d/wsgi-socket-prefix.conf")
        LOG.info("Fixing up: %s", colorizer.quote("/etc/httpd/conf.d/wsgi-socket-prefix.conf"))
        contents = "WSGISocketPrefix %s" % (sh.joinpths(self.log_dir, "wsgi-socket"))
        with sh.Rooted(True):
            # The name seems to need to come after wsgi.conf (so thats what we are doing)
            sh.write_file("/etc/httpd/conf.d/wsgi-socket-prefix.conf", contents)

    def _config_fix_httpd(self):
        LOG.info("Fixing up: %s", colorizer.quote('/etc/httpd/conf/httpd.conf'))
        (user, group) = self._get_apache_user_group()
        old_lines = sh.load_file('/etc/httpd/conf/httpd.conf').splitlines()
        new_lines = list()
        for line in old_lines:
            # Directives in the configuration files are case-insensitive,
            # but arguments to directives are often case sensitive...
            # NOTE(harlowja): we aren't handling multi-line fixups...
            if re.match("^\s*User\s+(.*)$", line, re.I):
                line = "User %s" % (user)
            if re.match("^\s*Group\s+(.*)$", line, re.I):
                line = "Group %s" % (group)
            if re.match("^\s*Listen\s+(.*)$", line, re.I):
                line = "Listen 0.0.0.0:80"
            new_lines.append(line)
        contents = utils.joinlinesep(*new_lines)
        with sh.Rooted(True):
            sh.write_file('/etc/httpd/conf/httpd.conf', contents)

    def _config_fixups(self):
        self._config_fix_wsgi()
        self._config_fix_httpd()


class RabbitRuntime(rabbit.RabbitRuntime):

    def _fix_log_dir(self):
        # This seems needed...
        #
        # Due to the following:
        # <<< Restarting rabbitmq-server: RabbitMQ is not running
        # <<< sh: /var/log/rabbitmq/startup_log: Permission denied
        # <<< FAILED - check /var/log/rabbitmq/startup_{log, _err}
        #
        # See: http://lists.rabbitmq.com/pipermail/rabbitmq-discuss/2011-March/011916.html
        # This seems like a bug, since we are just using service init and service restart...
        # And not trying to run this service directly...
        base_dir = sh.joinpths("/", 'var', 'log', 'rabbitmq')
        if sh.isdir(base_dir):
            with sh.Rooted(True):
                # Seems like we need root perms to list that directory...
                for fn in sh.listdir(base_dir):
                    if re.match("(.*?)(err|log)$", fn, re.I):
                        sh.chmod(sh.joinpths(base_dir, fn), 0666)

    def start(self):
        self._fix_log_dir()
        return rabbit.RabbitRuntime.start(self)

    def restart(self):
        self._fix_log_dir()
        return rabbit.RabbitRuntime.restart(self)


class NovaInstaller(nova.NovaInstaller):

    def _get_policy(self, ident_users):
        fn = LIBVIRT_POLICY_FN
        contents = LIBVIRT_POLICY_CONTENTS.format(idents=(";".join(ident_users)))
        return (fn, contents)

    def _get_policy_users(self):
        ident_users = set()
        ident_users.add(DEF_IDENT)
        ident_users.add('unix-user:%s' % (sh.getuser()))
        return ident_users

    def configure(self):
        configs_made = nova.NovaInstaller.configure(self)
        driver_canon = nhelper.canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if driver_canon == 'libvirt':
            (fn, contents) = self._get_policy(self._get_policy_users())
            dirs_made = list()
            with sh.Rooted(True):
                # TODO check if this dir is restricted before assuming it isn't?
                dirs_made.extend(sh.mkdirslist(sh.dirname(fn)))
                sh.write_file(fn, contents)
            self.tracewriter.cfg_file_written(fn)
            self.tracewriter.dirs_made(*dirs_made)
            configs_made += 1
        return configs_made


class YumPackagerWithRelinks(yum.YumPackager):

    def _remove(self, pkg):
        response = yum.YumPackager._remove(self, pkg)
        if response:
            options = pkg.get('packager_options', {})
            links = options.get('links', [])
            for entry in links:
                src = entry['source']
                tgt = entry['target']
                if sh.islink(tgt):
                    sh.unlink(tgt)
        return response

    def _install(self, pkg):
        yum.YumPackager._install(self, pkg)
        options = pkg.get('packager_options', {})
        links = options.get('links', [])
        for entry in links:
            src = entry['source']
            tgt = entry['target']
            if not sh.islink(tgt):
                # This is actually a feature, EPEL must not conflict
                # with RHEL, so X pkg installs newer version in
                # parallel.
                #
                # This of course doesn't work when running from git
                # like anvil does....
                sh.symlink(src, tgt)
        return True
