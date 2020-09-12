#!/usr/bin/env python
# -*- encoding=utf8 -*-

from mttkinter.mtTkinter import *
from tkinter.ttk import *


class AskString(Toplevel):
    def __init__(self, title="", text="", initial_value="", root=None):
        super().__init__(root)

        self.result = ""
        self.parent = None
        self.standalone = True
        if root:
            self.parent = root
            self.standalone = False
        else:
            self.parent = Tk()
            self.parent.withdraw()

        self.wm_title(title or root.title() if root else "")

        f = Frame(self)
        if text:
            Label(f, text=text, justify=LEFT).grid(row=0, padx=5, sticky=W)

        self.string = StringVar()
        self.entry = Entry(f, textvariable=self.string)
        self.entry.grid(row=1, padx=5, sticky=W+E)
        if initial_value:
            self.string.set(initial_value)
            self.entry.icursor(END)

        f.pack()

        Button(self, text="OK", command=self.ok).pack(side=RIGHT)
        Button(self, text="Cancel", command=self.destroy).pack(side=RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        if root:
            self.geometry("+%d+%d" % (root.winfo_rootx()+50,
                                      root.winfo_rooty()+50))

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.destroy)

        self.deiconify()
        self.focus_set()
        self.grab_set()
        self.entry.focus()
        self.update()

        if root and root.winfo_viewable():
            self.transient(root)

    def ok(self, event=None):
        self.result = self.string.get()
        self.destroy(event)

    def destroy(self, event=None):
        if not self.standalone:
            self.parent.focus_set()
        else:
            self.parent.destroy()
        super().destroy()

__all__ = ["AskString", ]
