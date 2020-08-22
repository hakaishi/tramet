#!/usr/bin/env python
# -*- encoding=utf8 -*-

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import messagebox

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
        self.conf = self.load_file() or {"profiles": {}}

        self.geometry("350x300")
        self.geometry("+%d+%d" % (root.winfo_x()+50, root.winfo_y()+25))
        self.minsize(350, 300)

        list_frame = Frame(self)
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(fill=Y, side=RIGHT)

        self.list = Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode="single")
        scrollbar.config(command=self.list.yview)
        self.list.pack(fill=BOTH, expand=True)
        # self.list.bind("<<ListboxSelect>>", self.selection_changed)
        self.list.bind("<Double-Button>", self.on_double_click)
        self.list.bind("<Return>", self.on_double_click)
        self.list.bind("<Button-3>", self.context)
        self.list.bind("<Delete>", self.delete)
        self.list.bind("<FocusIn>", self.focus_in_)
        self.list.bind("<Up>", self.move_up)
        self.list.bind("<Down>", self.move_dwn)
        for p in self.conf["profiles"].keys():
            self.list.insert(END, p)

        list_frame.pack(fill=BOTH, expand=True)

        btn_frame = Frame(self)

        Button(btn_frame, text="Save", command=self.save).grid(row=1, column=0, pady=10)
        Button(btn_frame, text="Cancel", command=self.destroy).grid(row=1, column=1, pady=10)

        btn_frame.pack(fill=X, expand=True)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        Sizegrip(self).pack(side=RIGHT)

    def context(self, event=None):
        popup = Menu(self, tearoff=False)
        popup.add_command(label="create", command=lambda: self.on_double_click(None))
        if len(self.list.curselection()) > 0 or self.list.nearest(event.y) != -1:
            sel = self.list.curselection()
            if len(sel) == 0:
                sel = [self.list.nearest(event.y)]
            popup.add_command(label="edit", command=lambda: self.on_double_click(event, idx=sel[0]))
            popup.add_command(label="delete", command=lambda: self.delete(event, self.list.nearest(event.y)))
        popup.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, e, idx=-1):
        item = []
        if e:
            item = self.list.curselection()
        if len(item) == 0 and idx > -1:
            item = [idx, ]
        Editor(self, self.list.get(item[0]) if len(item) > 0 else None)

    def move_up(self, e):
        idx = self.list.curselection()
        if len(idx) > 0:
            if idx[0] > 0:
                self.list.select_clear(0, END)
                self.list.selection_set(idx[0]-1)
                self.list.activate(idx[0]-1)
        else:
            self.list.selection_set(0)
            self.list.activate(0)

    def focus_in_(self, e):
        idx = self.list.curselection()
        if len(idx) == 0:
            self.list.selection_set(0)
            self.list.activate(0)

    def move_dwn(self, e):
        idx = self.list.curselection()
        if len(idx) > 0:
            if idx[0]+1 < len(self.list.get(0, END)):
                self.list.select_clear(0, END)
                self.list.selection_set(idx[0]+1)
                self.list.activate(idx[0]+1)
        else:
            self.list.selection_set(0)
            self.list.activate(0)

    @staticmethod
    def load_file():
        try:
            with open("config", "r+") as file:
                return load(file)
        except Exception as e:
            print(e)
            return {"profiles": {}}

    @classmethod
    def save_file(cls, obj):
        try:
            with open("config", "w+") as file:
                dump(obj, file, indent=4)
        except Exception as e:
            print(e)

    def save(self):
        self.save_file(self.conf)
        self.root.conf = self.conf
        profs = list(self.conf["profiles"].keys())
        self.root.profileCB["values"] = profs
        if self.root.profileCB.get() == "please create a profile first" and len(profs) > 0:
            self.root.profileCB.current(0)
        self.root.set_profile()

        self.destroy()

    def delete(self, e=None, idx=-1):
        # if self.profile.get():
        #     self.conf.pop(self.profile.get(), None)
        sel = self.list.curselection()
        if len(sel) == 0 and idx >= 0:
            sel = [idx, ]
        if len(sel) > 0:
            okc = messagebox.askokcancel("Delete Profile", "Do you really want to delete %s?" % self.list.get(sel[0]), parent=self)
            if okc:
                del self.conf["profiles"][self.list.get(sel[0])]
                self.list.delete(sel[0])


class Editor(Toplevel):
    def __init__(self, root, item):
        super().__init__(root)

        self.root = root

        frame = Frame(self)

        Label(frame, text="Profile:").grid(row=0, column=0, sticky=W)
        self.profile = StringVar()
        self.profile.set("default")
        self.profile_edit = Entry(frame, textvariable=self.profile)
        self.profile_edit.grid(row=0, column=1, sticky=EW)

        Label(frame, text="Host:").grid(row=1, column=0, sticky=W)
        self.host = StringVar()
        host_edit = Entry(frame, textvariable=self.host)
        host_edit.grid(row=1, column=1, sticky=EW)

        Label(frame, text="Port:").grid(row=2, column=0, sticky=W)
        self.port = IntVar()
        self.port.set(22)
        port_spin = Spinbox(frame, from_=0, to=99999, textvariable=self.port)
        port_spin.grid(row=2, column=1, sticky=EW)

        Label(frame, text="User name:").grid(row=3, column=0, sticky=W)
        self.user = StringVar()
        user_edit = Entry(frame, textvariable=self.user)
        user_edit.grid(row=3, column=1, sticky=EW)

        Label(frame, text="Password:").grid(row=4, column=0, sticky=W)
        self.passwd = StringVar()
        pass_edit = Entry(frame, textvariable=self.passwd, show="*")
        pass_edit.grid(row=4, column=1, sticky=EW)

        Label(frame, text="Encoding:").grid(row=5, column=0, sticky=W)
        enc = ["utf8"]
        ext = list(map(lambda x: x[1]["encoding"],
                       self.root.conf["profiles"].items()))
        if len(ext) > 0:
            enc.extend(ext)
        self.encoding = Combobox(frame, values=list(set(enc)))
        self.encoding.grid(row=5, column=1, sticky=EW)
        self.encoding.current(0)

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

        Button(btn_frame, text="OK", command=self.ok).grid(row=0, column=0,
                                                             pady=10)
        Button(btn_frame, text="Cancel", command=self.destroy).grid(row=0,
                                                                    column=1,
                                                                    pady=10)

        btn_frame.pack(fill=X, expand=True)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        Sizegrip(self).pack(side=RIGHT)

        if item:
            data = self.root.conf["profiles"][item]
            self.profile.set(item)
            self.host.set(data.get("host"))
            self.port.set(data.get("port"))
            self.user.set(data.get("user"))
            self.passwd.set(data.get("password"))
            self.path.set(data.get("path"))
            self.encoding.set(data.get("encoding"))
            self.mode.set(data.get("mode"))

        self.bind("<Escape>", lambda e: self.destroy())

    def ok(self):
        if not self.profile.get().strip() or\
            not self.host.get().strip() or\
            not self.port.get() or\
            not self.user.get().strip() or\
            not self.path.get().strip() or\
            not self.encoding.get().strip() or\
                not self.mode.get().strip():

            messagebox.showerror("Input data incomplete.", "Please fill all fields.", parent=self)
            return

        if self.profile.get() in self.root.conf["profiles"]:
            yesno = messagebox.askyesno("Updating Profile", "Do you really want to update %s?" % self.profile.get(), parent=self)
            if not yesno:
                return

        self.root.conf["profiles"][self.profile.get()] = {
            "host": self.host.get(),
            "port": self.port.get(),
            "user": self.user.get(),
            "password": self.passwd.get(),
            "path": self.path.get(),
            "encoding": self.encoding.get(),
            "mode": self.mode.get()
        }

        if self.profile.get() not in self.root.list.get(0, END):
            self.root.list.insert(END, self.profile.get())

        self.destroy()


if __name__ == "__main__":
    from tkinter import Tk
    rt = Tk()
    c = Config(rt)
    rt.withdraw()
    rt.wait_window(c)
