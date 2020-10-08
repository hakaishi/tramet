#!/usr/bin/env python
# -*- encoding=utf8 -*-

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
        super().destroy()


__all__ = ["AskString", ]
