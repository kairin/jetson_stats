# -*- coding: UTF-8 -*-
# This file is part of the jetson_stats package (https://github.com/rbonghi/jetson_stats or http://rnext.it).
# Copyright (c) 2020 Raffaello Bonghi.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from os import path
# Logging
import logging
# Launch command
import subprocess as sp
# Create logger for jplotlib
logger = logging.getLogger(__name__)

FILENAME = "/swapfile"
SWAP_MAX_SIZE = 15
SWAP_MIN_SIZE = 2


class Swap(object):

    def __init__(self, dir_swap="", default=8):
        # Set default folder swap
        self.dir = dir_swap
        self.swap_info = {}
        # Define actual size and new size variable
        self.actual_size = 0
        self.new_size = default
        # Initialize auto mount
        self.auto = True
        # Load swap information
        self.update()

    def update(self):
        swap_status = sp.Popen(['jetson_swap', '--status', '--dir', str(self.dir)], stdout=sp.PIPE, stderr=sp.PIPE)
        out, _ = swap_status.communicate()
        if out:
            swap_data = out.decode("utf-8")
            swap_data = swap_data.split("\t")
            # Load swap informations
            self.swap_info['file'] = swap_data[0].strip()
            self.swap_info['type'] = swap_data[1].strip()
            self.swap_info['size'] = int(swap_data[2].strip()) / 1000000.0
            self.swap_info['used'] = int(swap_data[3].strip()) / 1000.0
            self.swap_info['priority'] = int(swap_data[4].strip())
            # Update size
            self.actual_size = int(self.swap_info['size'])
        else:
            self.swap_info = {}

    def increase(self):
        if self.size + 1 <= SWAP_MAX_SIZE:
            self.size += 1
            return True
        else:
            return False

    def decrease(self):
        if self.size - 1 >= SWAP_MIN_SIZE:
            self.size -= 1
            return True
        else:
            return False

    @property
    def file(self):
        return self.dir + FILENAME

    @property
    def size(self):
        return self.new_size

    @size.setter
    def size(self, val):
        self.new_size = val

    def __len__(self):
        return self.actual_size

    def clearCache(self):
        """
        Clear cache following https://coderwall.com/p/ef1gcw/managing-ram-and-swap
        """
        clear_cache = sp.Popen(['sysctl', 'vm.drop_caches=3'], stdout=sp.PIPE, stderr=sp.PIPE)
        out, _ = clear_cache.communicate()
        return True if out else False

    @property
    def enable(self):
        self.update()
        return True if self.swap_info else False

    @enable.setter
    def enable(self, value):
        if not isinstance(value, bool):
            raise Exception("Use a boolean")
        # Enable or disable swap
        if value:
            self._enable()
        else:
            self._disable()

    def _enable(self):
        # List swap command
        swap_cmd = ['jetson_swap', '--size', str(self.new_size), '--dir', str(self.dir)]
        # Add auto command if request
        if self.auto:
            swap_cmd += ['--auto']
        # Run script
        sp.Popen(swap_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    
    def _disable(self):
        # List swap command
        swap_cmd = ['jetson_swap', '--off', '--dir', str(self.dir)]
        # Run script
        sp.Popen(swap_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
        # Remove swapfile if exist
# EOF
    