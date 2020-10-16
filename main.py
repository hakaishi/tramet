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


from sys import exit
from os.path import getsize

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import filedialog, messagebox
from MyDialogs import *

from Config import Config
from Connection import Connection
from Search import SearchView


class MainView(Tk):
    """Main view"""
    def __init__(self):
        super().__init__()

        style = Style(self)

        self.f_img = PhotoImage(file="file.png")
        self.d_img = PhotoImage(file="folder.png")
        self.l_img = PhotoImage(file="link.png")

        self.tk_setPalette(activeBackground="azure", activeForeground="black", background="snow2",
                           disabledForeground="gray", foreground="black", hightlightBackground="cyan",
                           hightlightColor="black", insertBackground="white", selectColor="blue",
                           selectBackground="blue", selectForeground="white", troughColor="green")

        style.configure(".", activeBackground="azure", activeForeground="black", background="snow2",
                        disabledForeground="gray", foreground="black", hightlightBackground="cyan",
                        hightlightColor="black", insertBackground="white", selectColor="blue",
                        selectBackground="blue", selectForeground="white", troughColor="green",
                        fieldbackground="white smoke")
        style.configure("Treeview", background="white smoke")

        self.minsize(500, 400)

        self.wm_title("Tramet")

        self.profiles_open = False
        self.config_window = None

        self.search_open = False
        self.search_window = None

        self.conf = Config.load_file()

        if "window_size" in self.conf:
            self.geometry(self.conf["window_size"])
        else:
            self.geometry("650x500")

        self.enc = "utf-8"
        self.path = "/"
        self.mode = "SFTP"
        self.password = ""
        self.port = 22
        self.connection = None

        self.found = -1
        self.save_last_path = BooleanVar()
        self.save_last_path.set(False)

        self.menubar = Menu(self)
        self.configure(menu=self.menubar)

        self.filemenu = Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.filemenu.add_command(label="Profiles", command=self.open_profiles)
        self.filemenu.add_command(label="Exit", command=self.destroy)
        self.menubar.add_command(label="Search", command=self.find_files)
        self.optionbar = Menu(self.menubar, tearoff=False)
        self.optionbar.add_checkbutton(label="Save last Path", variable=self.save_last_path)
        self.menubar.add_cascade(label="Options", menu=self.optionbar)

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        frame = Frame(self)

        Label(frame, text="profile:").grid(row=0, column=0, sticky=W)
        self.profileCB = Combobox(frame, state="readonly",
                                  values=list(self.conf["profiles"].keys()))
        self.profileCB.bind("<<ComboboxSelected>>", self.set_profile)
        self.profileCB.grid(row=0, column=1, sticky=EW, columnspan=3)
        self.profileCB.set(
            "please select a profile" if len(self.conf["profiles"].keys()) > 0 else "please create a profile first")

        Label(frame, text="host:").grid(row=1, column=0, sticky=W)
        self.connectionCB = Combobox(frame, state="disabled", values=list(
            set(map(lambda x: x[1]["host"], self.conf["profiles"].items()))
        ))
        self.connectionCB.grid(row=1, column=1, sticky=EW, columnspan=1)

        Label(frame, text="mode:").grid(row=1, column=2, sticky=W, padx=3)
        self.modeL = Label(frame, text="SFTP", relief="ridge", borderwidth=2)
        self.modeL.grid(row=1, column=3, sticky=W)

        Label(frame, text="name:").grid(row=2, column=0, sticky=W)
        self.name = StringVar()
        self.nameE = Entry(frame, state="disabled", textvariable=self.name)
        self.nameE.grid(row=2, column=1, sticky=EW, columnspan=3)

        Label(frame, text="path:").grid(row=3, column=0, sticky=W)
        self.path = StringVar()
        self.pathE = Entry(frame, textvariable=self.path)
        self.pathE.grid(row=3, column=1, sticky=EW, columnspan=3)
        self.pathE.bind('<Control-KeyRelease-a>', self.select_all)
        self.pathE.bind('<Return>', lambda e: self.cwd_dnl(e, ignore_item=True))
        self.pathE.bind("<FocusIn>", lambda e: self.focus())
        self.pathE.bind("<FocusIn>", lambda e: self.grab_set())
        self.pathE.bind("<FocusOut>", lambda e: self.pathE.grab_release())

        self.connect_btn = Button(frame, text="Load", command=self.connect)
        self.connect_btn.grid(row=4, column=0, columnspan=4, sticky=EW, pady=10)

        frame.grid(row=0, column=0, sticky=EW)
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)

        tree_frame = Frame(self)

        scrollbar = Scrollbar(tree_frame, takefocus=0)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.tree = Treeview(tree_frame, columns=("mode", "date", "size", "uid", "gid"),
                             selectmode="extended", yscrollcommand=scrollbar.set)
        self.tree.heading("#0", text="name")
        self.tree.column("#0", minwidth=100, width=100, stretch=True)
        self.tree.heading("mode", text="mode")
        self.tree.column("mode", minwidth=90, width=90, stretch=False)
        self.tree.heading("date", text="date")
        self.tree.column("date", minwidth=150, width=150, stretch=False)
        self.tree.heading("size", text="size")
        self.tree.column("size", minwidth=80, width=80, stretch=False)
        self.tree.heading("uid", text="uid")
        self.tree.column("uid", minwidth=50, width=60, stretch=False)
        self.tree.heading("gid", text="gid")
        self.tree.column("gid", minwidth=50, width=60, stretch=False)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<Double-1>", self.cwd_dnl)
        self.tree.bind("<Return>", self.cwd_dnl)
        self.tree.bind("<Right>", self.cwd_dnl)
        self.tree.bind("<Left>", self.cwd_dnl)
        self.tree.bind("<BackSpace>", self.cwd_dnl)
        self.tree.bind("<Button-1>", self.selection)
        self.tree.bind('<FocusIn>', self.on_get_focus)
        self.tree.bind("<Button-3>", self.context)
        self.tree.bind_all("<Shift_L><F2>", self.rename)
        self.tree.bind("<Delete>", self.delete)
        self.bind_all("<F5>", self.fill)

        self._toSearch = StringVar()
        self.searchEntry = Entry(self.tree, textvariable=self._toSearch)
        self.tree.bind("<KeyPress>", self._keyOnTree)
        self._toSearch.trace_variable("w", self._search)
        self.searchEntry.bind("<Return>", self._search)
        self.searchEntry.bind("<Escape>", self._hideEntry)
        self.searchEntry.bind("<FocusOut>", self._hideEntry)

        scrollbar.config(command=self.tree.yview)

        tree_frame.grid(row=1, column=0, sticky=NSEW)

        self.ctx = None  # Context menu

        footer = Frame(self)
        self.progress = Progressbar(footer, mode="determinate")
        Sizegrip(footer).pack(side=RIGHT)
        self.progress.pack(fill=X, expand=True, side=RIGHT)

        footer.grid(row=2, column=0, sticky=EW)

        if len(self.conf["profiles"].keys()) > 0:
            c = self.conf.get("current_profile", "")
            if not c:
                self.profileCB.current(0)
            else:
                self.profileCB.current(list(self.conf["profiles"].keys()).index(c))
            self.set_profile()

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.mainloop()

    def _search(self, *args):
        """search in treeview and jump to object"""
        pattern = self._toSearch.get()
        # avoid search on empty string
        if len(pattern) > 0:
            self.search(pattern)

    def search(self, pattern, item=''):
        """search for pattern in treeview"""
        children = self.tree.get_children("")
        for i, child in enumerate(children):
            text = self.tree.item(child, 'text')
            if text == ".." or i <= self.found:
                continue
            if text.lower().startswith(pattern.lower()):
                self.found = i
                self.tree.see(child)
                self.tree.selection_set(child)
                self.tree.focus(child)
                return True
            if i == len(children) - 1:
                self.found = -1

    def _keyOnTree(self, event):
        """trigger search on keypress excluding escape, backspace or tab"""
        if len(event.char) == 1 and event.keysym not in ["Escape", "BackSpace", "Tab"]:
            self.found = -1
            self.searchEntry.place(relx=1, anchor=NE)
            self.searchEntry.insert(END, event.char)
            self.searchEntry.focus_set()

    def _hideEntry(self, event):
        """hide search field"""
        self.searchEntry.delete(0, END)
        self.searchEntry.place_forget()
        self.tree.focus_set()

    def on_get_focus(self, event=None):
        """set focus and selection on receiving focus in"""
        if len(self.tree.selection()) == 0 and len(self.tree.get_children("")) > 0:
            self.tree.selection_set(self.tree.get_children('')[0])  # set selection on the first item
            self.tree.focus_set()
            self.tree.focus(self.tree.get_children('')[0])

    def select_all(self, e):
        """select all items"""
        # select text
        e.widget.select_range(0, END)
        # move cursor to the end
        e.widget.icursor(END)

    def set_profile(self, event=None):
        """set profile and reconnect"""
        p = self.profileCB.get()
        if p and p in self.conf["profiles"]:
            prof = self.conf["profiles"][p]
            self.connectionCB.set(prof["host"])
            self.port = prof["port"]
            self.name.set(prof["user"])
            self.pathE.delete(0, END)
            self.pathE.insert(END, prof["path"])
            self.enc = prof["encoding"]
            self.mode = prof["mode"]
            self.modeL["text"] = prof["mode"]
            self.password = prof["password"]
            self.save_last_path.set(prof.get("save_last_path", False))

            self.connection = Connection(
                prof["mode"],
                prof["host"],
                prof["port"],
                prof["user"],
                prof["password"],
                prof["encoding"],
                prof["path"],
                ui=self
            )

    def open_profiles(self):
        """open profile settings dialog or raise & focus it"""
        if not self.profiles_open:
            self.profiles_open = True
            self.config_window = Config(self)
        else:
            self.config_window.tkraise(self)
            self.config_window.focus()

    def selection(self, e=None):
        """close & destroy context menu on selection change event"""
        if self.ctx:
            self.ctx.destroy()
            self.ctx = None

    def find_files(self, event=None):
        """open file search dialog or raise & focus it"""
        if not self.search_open:
            self.search_open = True
            self.search_window = SearchView(self, self.path.get())
        else:
            self.search_window.tkraise(self)
            self.search_window.focus()

    def update_progress(self, maximum=None, value=None, step=None, mode=None, start=None, stop=None):
        """
        update progress from threads

        :param maximum: set maximum of progress bar
        :type maximum: int
        :param value: set value of progress bar
        :type value: int
        :param step: set step of progress bar
        :type step: int
        :param mode: set mode of progress bar
        :type mode: str
        :param start: flag to call start on progress bar
        :type start: bool
        :param stop: flag to stop progress bar
        :type stop: bool
        """
        if maximum:
            self.progress.configure(maximum=maximum)
        if value:
            self.progress.configure(value=value)
        if step:
            self.progress.step(step)
        if mode:
            self.progress.configure(mode=mode)
        if start:
            self.progress.start()
        if stop:
            self.progress.stop()

    def worker_done(self, refresh=False, message="", path=None, selected=""):
        """
        actions to be executed on finish

        :param refresh: flag to trigger refreshing of the treeview listing
        :type refresh: bool
        :param message: show message when queue got empty
        :type message: str
        :param path: set current workpath
        :type path: str
        :param selected: select item
        :type selected: str
        """
        if path:
            self.path.set(path)
        if message and self.connection._worker.q.empty():
            messagebox.showinfo("DONE", message, parent=self)
            self.update_progress(mode="determinate", stop=True, value=0)
        if refresh:
            self.connection.get_listing(self, self.connection.cwd, self.fill_tree_done, selected=selected)

    def cwd_dnl(self, event=None, ignore_item=False):
        """
        Change dir if item is a dir, else download

        :param event: activation event
        :param ignore_item: change folder (do not try to download)
        :type ignore_item: bool
        """
        self.progress.configure(value=0)

        self.selection()

        item = ""
        p = ""
        item_name = ""
        if not ignore_item:
            if str(event.type) == "ButtonPress":
                item = self.tree.identify('item', event.x, event.y)
            if event.keysym in ["Return", "Right"]:
                sel = self.tree.selection()
                if len(sel) > 0:
                    item = self.tree.selection()[0]
            elif event.keysym in ["BackSpace", "Left"]:
                item = self.tree.get_children("")[0]
                if self.path.get() == "/":
                    return

            item_name = self.tree.item(item, "text")
            if item_name == "..":
                p += "/".join(self.path.get().split("/")[:-1]) or "/"
            else:
                p += self.path.get()
                p = "/".join(((p if p != "/" else ""), item_name))

            if item:
                self.connection.cwd_dnl(self, p,
                                        [
                                            item_name,
                                            self.tree.item(item, "values")[0],
                                            self.tree.item(item, "values")[1],
                                            self.tree.item(item, "values")[2]
                                        ], self.update_progress, self.worker_done)
        else:
            p = self.path.get()
            self.connection.cwd_dnl(self, p, None, self.update_progress, self.worker_done)

    def fill_tree_done(self):
        """scroll to first item after all objects are displayed"""
        self.tree.focus_set()
        if len(self.tree.get_children("")) > 0:
            itm = self.tree.get_children("")[0]
            self.tree.see(itm)
            self.tree.focus(itm)

    def fill(self, event=None):
        """fill treeview with data"""
        self.connection.get_listing(self, self.path.get(), self.fill_tree_done)

    def context(self, e):
        """create a context menu"""
        self.ctx = Menu(self, tearoff=False)
        # iid = self.tree.identify_row(e.y)
        sel = self.tree.selection()
        if len(sel) > 0:
            selection = []
            for s in sel:
                item = self.tree.item(s)
                if item["values"][0][0] == "l":
                    messagebox.showwarning("Not supported",
                                           "Can't download links yet. Skipping link.",
                                           parent=self)
                    continue
                selection.append(item)

            self.ctx.add_command(
                label="Download Selected",
                command=lambda: self.connection.download_multi(self, selection, self.update_progress, self.worker_done)
            )
        # else:
        #     if iid and self.tree.item(iid, "values")[0][0] == "d":
        #         self.ctx.add_command(
        #             label="Download Folder",
        #             command=lambda:
        #                 self.download_folder(self.tree.item(iid, "text"))
        #         )
        self.ctx.add_command(label="Rename", command=self.rename)
        self.ctx.add_command(label="Create new Folder", command=self.mkdir)
        self.ctx.add_command(label="Upload Folder", command=self.upload_folder)
        self.ctx.add_command(label="Upload Files", command=self.upload_file)
        self.ctx.add_command(label="Delete", command=self.delete)
        self.ctx.tk_popup(e.x_root, e.y_root)

    def mkdir(self):
        """create a new folder"""
        a = AskString(self, "Create Directory",
                      "Enter a name for the new directory:")
        self.wait_window(a)
        name = a.result

        if name and name.strip():
            self.connection.mkdir(self, name, self.worker_done)

    def delete(self, event=None):
        """delete the selected objects"""
        def callback(index):
            self.tree.delete(index)

        idx = self.tree.selection()
        if len(idx) > 0:
            yesno = messagebox.askyesno(
                "Delete Selected",
                "Are you sure you want to delete the selected objects?",
                parent=self
            )
            if yesno:
                rmlist = []
                for i in idx:
                    rmlist.append([i, self.tree.item(i, "text"), self.tree.item(i, "values")[0]])

                self.connection.delete_object(self, rmlist, callback)

    def rename(self, event=None):
        """rename the selected object"""
        idx = self.tree.selection()
        if len(idx) > 0:
            if self.tree.item(idx[0], "text") in ["..", "."]:
                return
            a = AskString(self, "Rename",
                          "Enter new name for %s:" % self.tree.item(idx[0], "text"),
                          initial_value=self.tree.item(idx[0], "text"))
            self.wait_window(a)
            name = a.result

            def callback():
                self.tree.item(idx[0], text=name)

            if name and name.strip():
                self.connection.rename(self, self.tree.item(idx[0], "text"), name, callback)

    def upload_file(self):
        """upload local files"""
        size_all = 0
        files = filedialog.askopenfilenames(title="Choose files to upload",
                                            parent=self)

        dest = ""
        if len(files) > 0:
            a = AskString(self, "Choose destination",
                          "Choose upload destination",
                          initial_value=self.path.get())
            self.wait_window(a)
            dest += a.result

        if len(files) > 0 and dest:
            self.progress.configure(mode="indeterminate", value=0)
            self.progress.start()
            for f in files:
                size_all += getsize(f)
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=size_all)

            self.connection.upload_files(self, files, dest, self.update_progress, self.worker_done)

    def upload_folder(self):
        """upload a local folder"""
        folder = filedialog.askdirectory(
            title="Choose folder to upload", parent=self
        )

        dest = ""
        if folder:
            a = AskString(self, "Choose upload destination",
                          "Input upload destination path",
                          initial_value=self.path.get())
            self.wait_window(a)
            dest += a.result

        if folder and dest:
            self.connection.upload_folder(self, folder, dest, self.update_progress, self.worker_done)

    # def keep_alive(self):
    #     if not self.keep_alive_timer_running and self.connected:
    #         t = Timer(10, self.keep_alive_worker)
    #         t.setDaemon(True)
    #         t.start()
    #
    # def keep_alive_worker(self):
    #     if self.connected:
    #         if self.mode == "SFTP":
    #             if not self.is_busy:
    #                 try:
    #                     transport = self.connection.get_transport()
    #                     transport.send_ignore()
    #                 except EOFError:
    #                     self.connected = False
    #
    #         else:  # FTP
    #             if not self.is_busy:
    #                 try:
    #                     self.connection.voidcmd("NOOP")
    #                 except Exception:
    #                     self.connected = False
    #
    #         if not self.connected:
    #             self.connect_btn["text"] = "Connect"
    #
    #     self.keep_alive_timer_running = False
    #     if self.connected:
    #         self.keep_alive()

    def connect(self):
        """(Re-)connect"""
        p = self.profileCB.get()

        if self.profileCB.get() == "please select a profile":
            text = "Please select a profile to connect to."
            if len(self.profileCB["values"]) == 0:
                text = "Please create a profile first."
            messagebox.showinfo("No connection data", text, parent=self)
            return

        if p and p in self.conf["profiles"]:
            prof = self.conf["profiles"][p]

            self.connection.connect(
                prof["mode"], prof["host"], prof["port"], prof["user"],
                prof["password"], prof["encoding"], prof["path"], self
            )

    def disconnect(self):
        """disconnect"""
        prof = self.conf["profiles"][self.profileCB.get()]
        if self.save_last_path.get():
            prof["save_last_path"] = True
            prof["path"] = self.path.get()
        else:
            prof["save_last_path"] = False

        def cb():
            self.progress.configure(value=0)
            self.tree.delete(*self.tree.get_children())

        self.connection.disconnect(cb)

    def destroy(self):
        """close and destroy the application"""
        prof = self.conf["profiles"][self.profileCB.get()]
        if self.save_last_path.get():
            prof["save_last_path"] = True
            prof["path"] = self.path.get()
        else:
            prof["save_last_path"] = False
        self.conf["current_profile"] = self.profileCB.get()
        self.conf["window_size"] = f"{self.winfo_width()}x{self.winfo_height()}"
        Config.save_file(self.conf)
        self.connection.quit()
        super().destroy()


if __name__ == "__main__":
    MainView()
    exit()
