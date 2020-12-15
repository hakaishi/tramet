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


from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import StringVar


class AskString(Toplevel):
    def __init__(self, root, title="", text="", initial_value=""):
        super().__init__(root)

        self.result = ""
        self.parent = root

        self.wm_title(title or root.title() if root else "")

        self.geometry("400x100+%d+%d" % (root.winfo_x() + 50, root.winfo_y() + 25))

        f = Frame(self)
        if text:
            Label(f, text=text, justify=LEFT).grid(row=0, padx=5)

        self.string = StringVar()
        self.entry = Entry(f, textvariable=self.string)
        self.entry.grid(row=1, padx=5, sticky=EW)
        f.grid_columnconfigure(0, weight=1)
        if initial_value:
            self.string.set(initial_value)
            self.entry.icursor(END)
            self.entry.xview(END)

        f.pack(fill=X)

        Button(self, text="OK", command=self.ok).pack(side=RIGHT)
        Button(self, text="Cancel", command=self.destroy).pack(side=RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        if root:
            self.geometry("+%d+%d" % (root.winfo_rootx()+50,
                                      root.winfo_rooty()+50))

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.destroy)

        self.deiconify()
        self.focus()
        self.focus_set()
        self.grab_set()
        self.entry.focus()
        self.update_idletasks()
        self.update()
        self.lift()

        if root and root.winfo_viewable():
            self.transient(root)

        # root.wait_window(self)

    def ok(self, event=None):
        self.result = self.string.get()
        self.destroy()

    def destroy(self, event=None):
        self.parent.focus_set()
        super(AskString, self).destroy()


__all__ = ["AskString", ]
