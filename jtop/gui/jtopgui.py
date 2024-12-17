# -*- coding: UTF-8 -*-
# This file is part of the jetson_stats package (https://github.com/rbonghi/jetson_stats or http://rnext.it).
# Copyright (c) 2019-2023 Raffaello Bonghi.
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

import re
import abc
import curses
# Logging
import logging
# Timer
from datetime import datetime, timedelta
# Get variables
from ..core.common import get_var
# Graphics elements
from .lib.colors import NColors
from .lib.common import check_curses, set_xterm_title
# Create logger
logger = logging.getLogger(__name__)
# Initialization abstract class
# In according with: https://gist.github.com/alanjcastonguay/25e4db0edd3534ab732d6ff615ca9fc1
ABC = abc.ABCMeta('ABC', (object,), {})
# Gui refresh rate
GUI_REFRESH = 20 # 1000 // 20
# Copyright small
COPYRIGHT_SMALL_RE = re.compile(r""".*__cr__ = ["'](.*?)['"]""", re.S)


class Page(ABC):

    def __init__(self, name, stdscr, jetson):
        self.name = name
        self.stdscr = stdscr
        self.jetson = jetson
        self.dialog_window = None

    def setcontroller(self, controller):
        self.controller = controller

    def size_page(self):
        height, width = self.stdscr.getmaxyx()
        first = 0
        # Remove a line for sudo header
        if self.controller.message:
            height -= 1
            first = 1
        return height, width, first

    def register_dialog_window(self, dialog_window_object):
        self.dialog_window = dialog_window_object

    @abc.abstractmethod
    @check_curses
    def draw(self, key, mouse):
        pass

    def keyboard(self, key):
        pass


class JTOPGUI:
    """
        The easiest way to use curses is to use a wrapper around a main function
        Essentially, what goes in the main function is the body of your program,
        The `stdscr' parameter passed to it is the curses screen generated by our
        wrapper.
    """

    def __init__(self, stdscr, jetson, pages, init_page=0, start=True, loop=False, seconds=5, color_filter=False):
        # Initialize colors
        NColors(color_filter)
        # Set curses reference, refresh and jetson controller
        self.stdscr = stdscr
        self.jetson = jetson
        self.message = False
        # Initialize all Object pages
        self.pages = []
        for obj in pages:
            page = obj(stdscr, jetson)
            page.setcontroller(self)
            self.pages += [page]
        # Set default page
        self.n_page = 0
        self.set(init_page)
        # Initialize keyboard status
        self.key = -1
        self.old_key = -1
        # Initialize mouse
        self.mouse = ()
        # Run the GUI
        if start:
            self.run(loop, seconds)

    def run(self, loop, seconds):
        # In this program, we don't want keystrokes echoed to the console,
        # so we run this to disable that
        curses.noecho()
        # Additionally, we want to make it so that the user does not have to press
        # enter to send keys to our program, so here is how we get keys instantly
        curses.cbreak()
        # Try to hide the cursor
        if hasattr(curses, 'curs_set'):
            try:
                curses.curs_set(0)
            except Exception:
                pass
        # Lastly, keys such as the arrow keys are sent as funny escape sequences to
        # our program. We can make curses give us nicer values (such as curses.KEY_LEFT)
        # so it is easier on us.
        self.stdscr.keypad(True)
        # Enable mouse mask
        _, _ = curses.mousemask(curses.BUTTON1_CLICKED)
        # Refreshing page curses loop
        # https://stackoverflow.com/questions/54409978/python-curses-refreshing-text-with-a-loop
        self.stdscr.nodelay(1)
        # Using current time
        old = datetime.now()
        # Here is the loop of our program, we keep clearing and redrawing in this loop
        while not self.events() and self.jetson.ok(spin=True):
            # Get page selected
            page = self.pages[self.n_page]
            # Check if dialog window is open and disable mouse event on main pages
            record_mouse = self.mouse
            if page.dialog_window and page.dialog_window.enable_dialog_window:
                self.mouse = ()
            # Draw pages
            self.draw(page)
            self.mouse = record_mouse
            # Draw dialog window if it exists
            if page.dialog_window:
                page.dialog_window.show(self.stdscr, self.key, self.mouse)
            # Increase page automatically if loop enabled
            if loop and datetime.now() - old >= timedelta(seconds=seconds):
                self.increase(loop=True)
                old = datetime.now()

    def draw(self, page):
        # First, clear the screen
        self.stdscr.erase()
        # Write head of the jtop
        self.header()
        # Draw the page
        page.draw(self.key, self.mouse)
        # Draw menu
        self.menu()
        # Draw the screen
        self.stdscr.refresh()
        # Set a timeout and read keystroke
        self.stdscr.timeout(GUI_REFRESH)

    def increase(self, loop=False):
        # check reset
        if loop and self.n_page >= len(self.pages) - 1:
            idx = 0
        else:
            idx = self.n_page + 1
        # Fix set new page
        self.set(idx + 1)

    def decrease(self, loop=False):
        # check reset
        if loop and self.n_page <= 0:
            idx = len(self.pages) + 1
        else:
            idx = self.n_page + 1
        self.set(idx - 1)

    def set(self, idx):
        if idx <= len(self.pages) and idx > 0:
            self.n_page = idx - 1

    def title_terminal(self):
        status = []
        # Title script
        # Reference: https://stackoverflow.com/questions/25872409/set-gnome-terminal-window-title-in-python
        # Read NVP model
        if self.jetson.nvpmodel is not None:
            status += [self.jetson.nvpmodel.name.replace('MODE_', '').replace('_', ' ')]
        # Load CPU status
        idle = 100 - self.jetson.cpu['total']['idle']
        status += ["CPU {idle:.1f}%".format(idle=idle)]
        # Read GPU status
        if self.jetson.gpu:
            gpu = list(self.jetson.gpu.values())[0]
            load = gpu['status']['load']
            status += ["GPU {idle:.1f}%".format(idle=load)]
        str_xterm = '|'.join(status)
        # Print jtop basic info
        set_xterm_title("jtop {name}".format(name=str_xterm))

    @check_curses
    def header(self):
        self.title_terminal()
        # Detect if jtop is running on jetson or on other platforms
        if self.jetson.board['platform']['Machine'] == 'x86_64':
            self.header_x86()
        elif 'L4T' in self.jetson.board['hardware']:
            self.header_jetson()
        else:
            self.stdscr.addstr(0, 0, "Unrecognized hardware", curses.A_BOLD)

    def header_x86(self):
        platform = self.jetson.board['platform']
        release = platform['Release'].split("-")[0]
        message = "{system} {machine} machine - {distribution} [{release}]".format(system=platform['System'].upper(),
                                                                                   machine=platform['Machine'],
                                                                                   distribution=platform['Distribution'],
                                                                                   release=release)
        self.stdscr.addstr(0, 0, message, curses.A_BOLD)

    def header_jetson(self):
        model = self.jetson.board['hardware']["Model"]
        jetpack = self.jetson.board['hardware']["Jetpack"]
        L4T = self.jetson.board['hardware']["L4T"]
        # Write title
        idx = 0
        if self.jetson.interval != self.jetson.interval_user:
            self.message = True
            _, width = self.stdscr.getmaxyx()
            self.stdscr.addstr(0, 0, ("{0:<" + str(width) + "}").format(" "), NColors.iyellow())
            user = int(self.jetson.interval_user * 1000)
            interval = int(self.jetson.interval * 1000)
            string_sudo = "I CANNOT SET SPEED AT {user}ms - SERVER AT {interval}ms".format(user=user, interval=interval)
            self.stdscr.addstr(0, (width - len(string_sudo)) // 2, string_sudo, NColors.iyellow())
            idx = 1
        # Write first line
        head_string = "Model: {model} - ".format(model=model) if model else ""
        if jetpack:
            head_string += "Jetpack {jetpack} [L4T {L4T}]".format(jetpack=jetpack, L4T=L4T)
            self.stdscr.addstr(idx, 0, head_string, curses.A_BOLD)
        else:
            head_string += "[L4T {L4T}]".format(L4T=L4T)
            # Print only the model
            self.stdscr.addstr(idx, 0, head_string, curses.A_BOLD)
            # Print error message
            self.stdscr.addstr(idx, len(head_string) + 1, "Jetpack NOT DETECTED", NColors.red() | curses.A_BOLD)

    @check_curses
    def menu(self):
        height, width = self.stdscr.getmaxyx()
        # Set background for all menu line
        self.stdscr.addstr(height - 1, 0, ("{0:<" + str(width - 1) + "}").format(" "), curses.A_REVERSE)
        position = 1
        for idx, page in enumerate(self.pages):
            color = curses.A_NORMAL if self.n_page == idx else curses.A_REVERSE
            self.stdscr.addstr(height - 1, position, str(idx + 1), color | curses.A_BOLD)
            self.stdscr.addstr(height - 1, position + 1, page.name + " ", color)
            position += len(page.name) + 3
        # Quit button
        self.stdscr.addstr(height - 1, position, "Q", curses.A_REVERSE | curses.A_BOLD)
        self.stdscr.addstr(height - 1, position + 1, "uit ", curses.A_REVERSE)
        # Author name
        name_author = get_var(COPYRIGHT_SMALL_RE) + " "
        self.stdscr.addstr(height - 1, width - len(name_author), name_author, curses.A_REVERSE)

    def event_menu(self, mx, my):
        height, _ = self.stdscr.getmaxyx()
        # Check if is an event menu
        if my == height - 1:
            # Check which page
            position = 1
            for idx, page in enumerate(self.pages):
                size = len(page.name) + 3
                # Check if mouse is inside menu name
                if mx >= position and mx < position + size:
                    # Set new page
                    self.set(idx + 1)
                    return False
                # Increase counter
                position += size
            # Quit button
            if mx >= position and mx < position + 4:
                return True
        return False

    def events(self):
        event = self.stdscr.getch()
        # Run keyboard check
        status_mouse = False
        status_keyboard = self.keyboard(event)
        # Clear event mouse
        self.mouse = ()
        # Check event mouse
        if event == curses.KEY_MOUSE:
            try:
                _, mx, my, _, _ = curses.getmouse()
                # Run event menu controller
                status_mouse = self.event_menu(mx, my)
                self.mouse = (mx, my)
            except curses.error:
                pass
        return status_keyboard or status_mouse

    def keyboard(self, event):
        self.key = event
        if self.old_key != self.key:
            # keyboard check list
            if self.key == curses.KEY_LEFT:
                self.decrease(loop=True)
            elif self.key == curses.KEY_RIGHT or self.key == ord('\t'):
                self.increase(loop=True)
            elif self.key in [ord(str(n)) for n in range(10)]:
                num = int(chr(self.key))
                self.set(num)
            elif self.key == ord('q') or self.key == ord('Q') or self.ESC_BUTTON(self.key):
                # keyboard check quit button
                return True
            else:
                page = self.pages[self.n_page]
                # Run key controller
                page.keyboard(self.key)
            # Store old value key
            self.old_key = self.key
        return False

    def ESC_BUTTON(self, key):
        """
            Check there is another character prevent combination ALT + <OTHER CHR>
            https://stackoverflow.com/questions/5977395/ncurses-and-esc-alt-keys
        """
        if key == 27:
            n = self.stdscr.getch()
            if n == -1:
                return True
        return False
# EOF
