#!/usr/bin/env python
# -*- encoding=utf8 -*-

from tkinter import Toplevel, Listbox, END, StringVar, IntVar, BOTH, X, Y, EW, W, RIGHT
from tkinter.ttk import Combobox, Label, Frame, Entry, Button, Scrollbar, Sizegrip
try:
    from tkinter.ttk import Spinbox
except ImportError:
    class Spinbox(Entry):

        def __init__(self, master=None, **kw):
            Entry.__init__(self, master, "ttk::spinbox", **kw)

        def set(self, value):
            self.tk.call(self._w, "set", value)

from json import dump, load


class Config(Toplevel):
    def __init__(self, root):
        super().__init__(root)

        self.root = root
        self.conf = self.load_file() or {}

        self.geometry("500x500")
        self.minsize(500, 500)

        list_frame = Frame(self)
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(fill=Y, side=RIGHT)

        self.list = Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode="single")
        scrollbar.config(command=self.list.yview)
        self.list.pack(fill=BOTH, expand=True)
        self.list.bind("<<ListboxSelect>>", self.selection_changed)
        self.list.bind("<FocusIn>", self.focus_in_)
        self.list.bind("<Up>", self.move_up)
        self.list.bind("<Down>", self.move_dwn)
        for p in self.conf.keys():
            self.list.insert(END, p)

        list_frame.pack(fill=BOTH, expand=True)

        frame = Frame(self)

        Label(frame, text="Profile:").grid(row=0, column=0, sticky=W)
        self.profile = StringVar()
        self.profile_edit = Entry(frame, textvariable=self.profile)
        self.profile_edit.grid(row=0, column=1, sticky=EW)

        Label(frame, text="Host:").grid(row=1, column=0, sticky=W)
        self.host = StringVar()
        host_edit = Entry(frame, textvariable=self.host)
        host_edit.grid(row=1, column=1, sticky=EW)

        Label(frame, text="Port:").grid(row=2, column=0, sticky=W)
        self.port = IntVar()
        self.port.set(22)
        port_spin = Spinbox(frame, textvariable=self.port)
        port_spin.grid(row=2, column=1, sticky=EW)

        Label(frame, text="User name:").grid(row=3, column=0, sticky=W)
        self.user = StringVar()
        user_edit = Entry(frame, textvariable=self.user)
        user_edit.grid(row=3, column=1, sticky=EW)

        Label(frame, text="Password:").grid(row=4, column=0, sticky=W)
        self.passwd = StringVar()
        pass_edit = Entry(frame, textvariable=self.passwd)
        pass_edit.grid(row=4, column=1, sticky=EW)

        Label(frame, text="Encoding:").grid(row=5, column=0, sticky=W)
        self.encoding = Combobox(frame, values=list(set(map(lambda x: x[1]["encoding"], self.conf.items()))))
        self.encoding.grid(row=5, column=1, sticky=EW)

        Label(frame, text="Mode:").grid(row=6, column=0, sticky=W)
        self.mode = Combobox(frame, values=("SFTP", "FTP"))
        self.mode.grid(row=6, column=1, sticky=EW)
        self.mode.current(0)

        Label(frame, text="Path:").grid(row=7, column=0, sticky=W)
        self.path = StringVar()
        self.path.set("/")
        path_edit = Entry(frame, textvariable=self.path)
        path_edit.grid(row=7, column=1, sticky=EW)

        frame.pack(fill=X, expand=True)
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)

        btn_frame = Frame(self)

        Button(btn_frame, text="Delete", command=self.delete).grid(row=0, column=0, pady=(10, 30))
        Button(btn_frame, text="Add/Update", command=self.add).grid(row=0, column=1, pady=(10, 30))
        Button(btn_frame, text="Save Config", command=self.save).grid(row=1, column=0, pady=10)
        Button(btn_frame, text="Cancel", command=self.destroy).grid(row=1, column=1, pady=10)

        btn_frame.pack(fill=X, expand=True)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        Sizegrip(self).pack(side=RIGHT)

    def selection_changed(self, event=None):
        if len(self.list.curselection()) > 0:
            self.profile.set(self.list.get(self.list.curselection()[0]))
            self.host.set(self.conf[self.profile.get()]["host"])
            self.port.set(self.conf[self.profile.get()]["port"])
            self.user.set(self.conf[self.profile.get()]["user"])
            self.passwd.set(self.conf[self.profile.get()]["password"])
            self.path.set(self.conf[self.profile.get()]["path"])
            self.encoding.set(self.conf[self.profile.get()]["encoding"])
            self.mode.set(self.conf[self.profile.get()]["mode"])

    def move_up(self, e):
        idx = self.list.curselection()
        if len(idx) > 0:
            if idx[0] > 0:
                self.list.select_clear(0, END)
                self.list.selection_set(idx[0]-1)
                self.list.activate(idx[0]-1)
                self.selection_changed()
        else:
            self.list.selection_set(0)
            self.list.activate(0)
            self.selection_changed()

    def focus_in_(self, e):
        idx = self.list.curselection()
        if len(idx) == 0:
            self.list.selection_set(0)
            self.list.activate(0)
            self.selection_changed()

    def move_dwn(self, e):
        idx = self.list.curselection()
        if len(idx) > 0:
            if idx[0]+1 < len(self.list.get(0, END)):
                self.list.select_clear(0, END)
                self.list.selection_set(idx[0]+1)
                self.list.activate(idx[0]+1)
                self.selection_changed()
        else:
            self.list.selection_set(0)
            self.list.activate(0)
            self.selection_changed()

    @staticmethod
    def load_file():
        try:
            with open("config", "r+") as file:
                return load(file)
        except Exception as e:
            print(e)
            return {}

    @classmethod
    def save_file(cls, obj):
        try:
            with open("config", "w+") as file:
                dump(obj, file, indent=4)
        except Exception as e:
            print(e)

    def add(self):
        self.conf[self.profile.get()] = {
            "host": self.host.get(),
            "port": self.port.get(),
            "user": self.user.get(),
            "password": self.passwd.get(),
            "path": self.path.get(),
            "encoding": self.encoding.get(),
            "mode": self.mode.get()
        }

        if self.profile.get() not in self.list.get(0, END):
            self.list.insert(END, self.profile.get())

    def save(self):
        self.save_file(self.conf)
        self.root.conf = self.conf
        self.root.profileCB["values"] = list(self.conf.keys())
        self.root.set_profile()

        self.destroy()

    def delete(self):
        if self.profile.get():
            self.conf.pop(self.profile.get(), None)
        if len(self.list.curselection()) > 0:
            for s in self.list.curselection():
                self.list.delete(s)
        else:
            for i in self.list.get(0, END):
                if self.profile.get() == i:
                    self.list.delete(self.list.get(0, END).index(i))


if __name__ == "__main__":
    from tkinter import Tk
    rt = Tk()
    c = Config(rt)
    rt.withdraw()
    rt.wait_window(c)
