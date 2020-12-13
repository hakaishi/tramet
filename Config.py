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


__all__ = ['Config', ]

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import messagebox

from sys import executable
from os.path import join, dirname, basename

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
    """Settings dialog - mainly profile settings"""
    def __init__(self, root):
        """
        Constructor of Config

        :param root: root Tk object
        :type root: Tk
        """
        super().__init__(root)

        self.root = root
        self.conf = self.load_file() or {"profiles": {}}

        self.editor_open = False
        self.editor_window = None

        self.geometry("350x300")
        self.geometry("+%d+%d" % (root.winfo_x()+50, root.winfo_y()+25))
        self.minsize(350, 300)

        self.wm_title("Tramet - Profiles")

        list_frame = Frame(self)
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(fill=Y, side=RIGHT)

        self.list = Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode="single", background="white smoke")
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
        """Context menu"""
        popup = Menu(self, tearoff=False)
        popup.add_command(label="create", command=lambda: self.on_double_click(None))
        if len(self.list.curselection()) > 0 or self.list.nearest(event.y) != -1:
            bbox = self.list.bbox(self.list.nearest(event.y))
            self.list.select_clear(0, END)
            if bbox[1] <= event.y < bbox[1]+bbox[3]:
                self.list.selection_set(self.list.nearest(event.y))

            sel = self.list.curselection()
            if len(sel) > 0:
                popup.add_command(label="edit", command=lambda: self.on_double_click(event, idx=sel[0]))
                popup.add_command(label="delete", command=lambda: self.delete(event, self.list.nearest(event.y)))
        popup.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, e, idx=-1):
        """Double click event to open or raise profile settings"""
        if e and idx < 0 < len(self.list.curselection()):
            idx = self.list.curselection()[0]
        if not self.editor_open:
            self.editor_open = True
            self.editor_window = Editor(self, self.list.get(idx) if idx >= 0 else None, idx)
        else:
            self.editor_window.tkraise(self)
            self.editor_window.focus()

    def move_up(self, e):
        """move selection up event"""
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
        """focus in event"""
        idx = self.list.curselection()
        if len(idx) == 0:
            self.list.selection_set(0)
            self.list.activate(0)

    def move_dwn(self, e):
        """move selection down event"""
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
        """load settings file"""
        try:
            with open(join(dirname(executable) if basename(executable) == "tramet" else "", "config"), "r+") as file:
                d = load(file)
                if "profiles" not in d:
                    d = {"profiles": {}}
                return d
        except Exception as e:
            print(e)
            return {"profiles": {}}

    @classmethod
    def save_file(cls, obj):
        """
        save settings object to settings file

        :param obj: settings object
        :type obj: dict
        """
        try:
            with open(join(dirname(executable) if basename(executable) == "tramet" else "", "config"), "w+") as file:
                dump(obj, file, indent=4, sort_keys=True)
        except Exception as e:
            print(e)

    def save(self):
        """save settings button pressed"""
        if self.root.connection:
            self.root.connection.quit()  # quit connection
        self.root.conf.update(self.conf)
        self.save_file(self.root.conf)
        profs = list(self.conf["profiles"].keys())
        self.root.profileCB["values"] = profs
        if (self.root.profileCB.get() == "please create a profile first"
                or self.root.profileCB.get() not in profs) and len(profs) > 0:
            self.root.profileCB.current(0)
        self.root.set_profile(True)

        self.destroy()

    def delete(self, e=None, idx=-1):
        """delete profile"""
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

    def destroy(self):
        """close & destroy settings dialog"""
        self.root.profiles_open = False
        self.root.config_window = None
        super().destroy()


class Editor(Toplevel):
    """profile editor dialog"""
    def __init__(self, root, item, idx=-1):
        """
        Contructor of Editor

        :param root: Config dialog
        :type root: Config
        :param item: Selected profile item
        :type item: Listbox item
        """
        super().__init__(root)

        self.root = root
        self.orig_item = item
        self.orig_idx = idx

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
        self.mode = Combobox(frame, values=("SFTP", "FTP"), state="readonly")
        self.mode.grid(row=6, column=1, sticky=EW)
        self.mode.current(0)

        Label(frame, text="Path:").grid(row=7, column=0, sticky=W)
        self.path = StringVar()
        # self.path.set("/")
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
        """ok button pressed - check and save profile settings"""
        if not self.profile.get().strip() or\
            not self.host.get().strip() or\
            not self.port.get() or\
            not self.user.get().strip() or\
            not self.encoding.get().strip() or\
                not self.mode.get().strip():

            messagebox.showerror("Input data incomplete.", "Please fill all fields.", parent=self)
            return

        if self.profile.get() in self.root.conf["profiles"]:
            yesno = messagebox.askyesno("Updating Profile", "Do you really want to update %s?" % self.profile.get(), parent=self)
            if not yesno:
                return

        # replace item in item list if name changed
        if self.orig_item and self.orig_item != self.profile.get():
            del self.root.conf["profiles"][self.orig_item]
            self.root.list.delete(self.orig_idx)
            self.root.list.insert(self.orig_idx, self.profile.get())

        self.root.conf["profiles"][self.profile.get()] = {
            "host": self.host.get(),
            "port": self.port.get(),
            "user": self.user.get(),
            "password": self.passwd.get(),
            "path": self.path.get(),
            "encoding": self.encoding.get(),
            "mode": self.mode.get(),
            "save_last_path": self.root.conf["profiles"].setdefault(self.profile.get(), {}).get("save_last_path", False)
        }

        # add item if not in list
        if self.profile.get() not in self.root.list.get(0, END):
            self.root.list.insert(END, self.profile.get())

        self.destroy()

    def destroy(self, event=None):
        """close & destroy profile editor dialog"""
        self.root.editor_open = False
        self.root.editor_window = None
        super().destroy()


if __name__ == "__main__":
    from tkinter import Tk
    rt = Tk()
    c = Config(rt)
    rt.withdraw()
    rt.wait_window(c)
