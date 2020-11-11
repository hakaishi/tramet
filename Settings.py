#!/usr/bin/env python
# -*- encoding=utf8 -*-

__copyright__ = """
    Tramet, a sftp/ftp client
    Copyright (C) 2020 Christian Metscher <hakaishi@web.de>

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.

    Tramet is licensed under the MIT, see `http://copyfree.org/licenses/mit/license.txt'.
"""
__license__ = "MIT"


__all__ = ['Settings', ]

from mttkinter.mtTkinter import *
from tkinter.ttk import *

try:
    from tkinter.ttk import Spinbox
except ImportError:
    class Spinbox(Entry):

        def __init__(self, master=None, **kw):
            Entry.__init__(self, master, "ttk::spinbox", **kw)

        def set(self, value):
            self.tk.call(self._w, "set", value)

from json import dump, load

from Config import Config


class Settings(Toplevel):
    """Settings dialog - mainly profile settings"""
    def __init__(self, root):
        """
        Constructor of Config

        :param root: root Tk object
        :type root: Tk
        """
        super().__init__(root)

        self.root = root

        self.geometry("350x300")
        self.geometry("+%d+%d" % (root.winfo_x()+50, root.winfo_y()+25))
        self.minsize(350, 300)

        self.wm_title("Tramet - Settings")

        self.conf = Config.load_file()

        def save(event=None):
            root.buffer_size = buf.get() * 1024 * 1024
            self.conf["buffer_size"] = buf.get() * 1024 * 1024
            self.destroy()

        buf = IntVar()
        buf.set(self.conf.get("buffer_size", 10*1024*1024) // 1024 // 1024)
        Label(self, text="File Buffer size (MB): ").grid(row=0, column=0, padx=(10, 0), pady=(10, 20))
        s = Spinbox(self, from_=1, to=999, textvariable=buf)
        s.grid(row=0, column=1)

        f = Frame(self)
        f.grid(row=1, column=0, columnspan=2, sticky=E)
        ok = Button(f, text="OK", command=save)
        ok.pack(side=RIGHT, padx=10, pady=10)
        cancel = Button(f, text="Cancel", command=self.destroy)
        cancel.pack(side=RIGHT, padx=10, pady=10)

    def destroy(self, event=None):
        """close & destroy profile editor dialog"""
        self.root.settings_open = False
        self.root.settings_window = None
        Config.save_file(self.conf)
        super().destroy()


if __name__ == "__main__":
    rt = Tk()
    s = Settings(rt)
    rt.withdraw()
    rt.wait_window(s)
