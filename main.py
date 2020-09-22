#!/usr/bin/env python
# -*- encoding=utf8 -*-

from sys import exit
from os import listdir, makedirs, utime, stat, remove
from os.path import exists, join, basename, getmtime, getatime, getsize, isdir, normpath, \
    dirname, abspath, isfile, islink
from stat import S_ISDIR, S_ISLNK, S_ISREG, filemode
from datetime import datetime
from threading import Timer

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import filedialog, messagebox
from MyDialogs import *

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ssh2.sftp import *
from ssh2.sftp_handle import SFTPAttributes
from ssh2.exceptions import *
from ftplib import FTP, error_perm

from Config import Config
from thread_work import *


class MainView(Tk):
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

        self.geometry("500x400")
        self.minsize(500, 400)

        self.wm_title("Tramet")

        self.profiles_open = False
        self.config_window = None

        self.conf = Config.load_file()
        self.worker = None

        self.enc = "utf-8"
        self.path = "/"
        self.mode = "SFTP"
        self.password = ""
        self.port = 22
        self.connection = None
        self.connected = False
        self.keep_alive_timer_running = False
        self.is_busy = False
        self.found = -1
        self.save_last_path = BooleanVar()
        self.save_last_path.set(False)

        self.menubar = Menu(self)
        self.configure(menu=self.menubar)

        self.filemenu = Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.filemenu.add_command(label="Profiles", command=self.open_profiles)
        self.filemenu.add_command(label="Exit", command=self.destroy)
        self.menubar.add_command(label="Search", command=self.find)
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

        self.connect_btn = Button(frame, text="Connect", command=self.connect)
        self.connect_btn.grid(row=4, column=0, columnspan=4, sticky=EW, pady=10)

        frame.grid(row=0, column=0, sticky=EW)
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)

        tree_frame = Frame(self)

        scrollbar = Scrollbar(tree_frame, takefocus=0)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.tree = Treeview(tree_frame, columns=("mode", "date", "size"),
                             selectmode="extended", yscrollcommand=scrollbar.set)
        self.tree.heading("#0", text="name")
        self.tree.column("#0", minwidth=100, width=100, stretch=True)
        self.tree.heading("mode", text="mode")
        self.tree.column("mode", minwidth=90, width=90, stretch=False)
        self.tree.heading("date", text="date")
        self.tree.column("date", minwidth=150, width=150, stretch=False)
        self.tree.heading("size", text="size")
        self.tree.column("size", minwidth=80, width=80, stretch=False)
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
        self.bind_all("<F5>", lambda e: self.fill(self.connection))

        self._toSearch = StringVar()
        self.searchEntry = Entry(self.tree, textvariable=self._toSearch)
        self.tree.bind("<KeyPress>", self._keyOnTree)
        self._toSearch.trace_variable("w", self._search)
        self.searchEntry.bind("<Return>", self._search)
        self.searchEntry.bind("<Escape>", self._hideEntry)
        self.searchEntry.bind("<FocusOut>", self._hideEntry)

        scrollbar.config(command=self.tree.yview)

        tree_frame.grid(row=1, column=0, sticky=NSEW)

        self.ctx = None

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
        pattern = self._toSearch.get()
        # avoid search on empty string
        if len(pattern) > 0:
            self.search(pattern)

    def search(self, pattern, item=''):
        children = self.tree.get_children("")
        for i, child in enumerate(children):
            text = self.tree.item(child, 'text')
            if text == ".." or i <= self.found:
                continue
            if text.lower().startswith(pattern.lower()):
                self.found = i
                self.tree.selection_set(child)
                self.tree.see(child)
                return True
            if i == len(children) - 1:
                self.found = -1

    def _keyOnTree(self, event):
        if len(event.char) == 1 and event.keysym not in ["Escape", "BackSpace", "Tab"]:
            self.found = -1
            self.searchEntry.place(relx=1, anchor=NE)
            self.searchEntry.insert(END, event.char)
            self.searchEntry.focus_set()

    def _hideEntry(self, event):
        self.searchEntry.delete(0, END)
        self.searchEntry.place_forget()
        self.tree.focus_set()

    def on_get_focus(self, event=None):
        if len(self.tree.selection()) == 0 and len(self.tree.get_children("")) > 0:
            self.tree.selection_set(self.tree.get_children('')[0])  # set selection on the first item
            self.tree.focus_set()
            self.tree.focus(self.tree.get_children('')[0])

    def select_all(self, e):
        # select text
        e.widget.select_range(0, END)
        # move cursor to the end
        e.widget.icursor(END)

    def set_profile(self, event=None):
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

            if event and self.connected:
                self.connect()  # disconnect

    def open_profiles(self):
        if not self.profiles_open:
            self.profiles_open = True
            self.config_window = Config(self)
        else:
            self.config_window.tkraise(self)
            self.config_window.focus()

    def selection(self, e=None):
        if self.ctx:
            self.ctx.destroy()
            self.ctx = None

    def find(self, event=None):  # todo
        messagebox.showinfo("Not yet", "Work in progress", parent=self)

    def download_worker(self, conn, src, file, ts, isFile=True, destination=""):
        if isFile:
            if destination:
                overwrite = True
                if exists(join(destination, file)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing file?",
                        "A file with the same name already exists. Do you want to override it?",
                        parent=self)
                if overwrite:
                    self.is_busy = True
                    if self.mode == "SFTP":
                        # print(src)
                        try:
                            res = conn.session.scp_recv2(src)
                            if res:
                                with open(join(destination, file), "wb+") as f:
                                    size = 0
                                    while True:
                                        siz, tbuff = res[0].read(1024*10)
                                        if siz < 0:
                                            print("error code:", siz)
                                            res[0].close()
                                            break
                                        size += siz
                                        if size > res[1].st_size:
                                            sz = size - res[1].st_size
                                            f.write(tbuff[:sz])
                                            self.progress.step(sz)
                                        else:
                                            f.write(tbuff)
                                            self.progress.step(siz)
                                        if size >= res[1].st_size:
                                            res[0].close()
                                            break
                                utime(join(destination, file), (res[1].st_atime, res[1].st_mtime))
                        except SCPProtocolError:
                            messagebox.showerror("Insufficient Permissions",
                                                 "Could not receive file because of insufficient permissions.",
                                                 parent=self)
                        except Exception as e:
                            print("unknown error: ", e)

                    else:
                        try:
                            def handleDownload(block, fi):
                                fi.write(block)
                                self.progress.step(len(block))
                            with open(join(destination, file), "wb+") as f:
                                conn.retrbinary("RETR %s" % join(src, file), lambda blk: handleDownload(blk, f))
                            utime(join(destination, file), ts)
                        except error_perm:
                            messagebox.showerror("Insufficient Permissions",
                                                 "Could not receive file because of insufficient permissions.",
                                                 parent=self)
                            remove(join(destination, file))
        else:
            if destination:
                overwrite = True
                if exists(join(destination, file)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing files?",
                        "A folder with the same name already exists. Do you want to override all contained files?",
                        parent=self)
                else:
                    makedirs(join(destination, file), exist_ok=True)
                if overwrite:
                    self.is_busy = True

                    if self.mode == "SFTP":
                        def recurse(orig, path, fi):
                            if S_ISDIR(fi[1].permissions) != 0:
                                makedirs(path, exist_ok=True)
                                with conn.opendir(orig) as dirh_:
                                    for size_, buf_, attrs_ in dirh_.readdir():
                                        o_ = buf_.decode(self.enc)
                                        if o_ not in [".", ".."]:
                                            recurse(join(orig, o_), join(path, o_), (o_, attrs_))
                            elif S_ISREG(fi[1].permissions) != 0:
                                res_ = None
                                try:
                                    res_ = conn.session.scp_recv2(orig)
                                except SCPProtocolError:
                                    messagebox.showerror("Download Error", "Could not recieve %s" % basename(orig),
                                                         parent=self)
                                if res_:
                                    with open(path, "wb+") as fil:
                                        size_ = 0
                                        while True:
                                            si, tbuf = res_[0].read()
                                            if si < 0:
                                                print("error code:", si)
                                                res_[0].close()
                                                break
                                            size_ += si
                                            if size_ > res_[1].st_size:
                                                fil.write(tbuf[:(res_[1].st_size - size_)])
                                                res_[0].close()
                                                break
                                            else:
                                                fil.write(tbuf)
                                            if size_ == res_[1].st_size:
                                                res_[0].close()
                                                break
                                    utime(path,
                                          (res_[1].st_atime, res_[1].st_mtime))

                        # for obj in conn.listdir_attr(
                        #         src, encoding=self.enc
                        # ):
                        #     recurse(src, obj)
                        size_all = {"size": 0}
                        self.progress.configure(mode="indeterminate")
                        self.progress.start()

                        def recrse(pth, obj, attr, rslt):
                            if S_ISDIR(attr.permissions) != 0:
                                with conn.opendir(join(pth, obj)) as dirh_:
                                    for size_, buf_, attrs_ in dirh_.readdir():
                                        o_ = buf_.decode(self.enc)
                                        if o_ not in [".", ".."]:
                                            recrse(join(pth, obj), o_, attrs_, rslt)
                            elif S_ISREG(attrs.permissions) != 0:
                                rslt["size"] += attrs.filesize

                        with conn.opendir(src) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                o = buf.decode(self.enc)
                                if o not in [".", ".."]:
                                    recrse(src, o, attrs, size_all)
                        self.progress.stop()
                        self.progress.configure(mode="determinate", maximum=size_all["size"])

                        with conn.opendir(src) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                o = buf.decode(self.enc)
                                if o not in [".", ".."]:
                                    recurse(join(src, o), join(destination, file, o), (o, attrs))
                        print("done")
                    else:  # FTP
                        def recurse(path, fi):
                            # print(path, fi)
                            if fi[0] == "d":
                                makedirs(join(destination, file, basename(path)), exist_ok=True)
                                data = {}
                                dinfo = []
                                conn.dir(path, dinfo.append)
                                dfiles = conn.nlst(path)
                                for f_ in sorted(dfiles, key=lambda x: (x.lower(), len(x))):
                                    fin = basename(f_)
                                    for ifo in sorted(dinfo, key=lambda x: (x.lower(), len(x))):
                                        if fin == ifo[-len(fin):]:
                                            data[fin] = ifo[:-len(fin)]
                                            dinfo.remove(ifo)
                                            break
                                for x in data.items():
                                    recurse(join(path, x[0]), x[1])
                            elif fi[0] == "-":
                                # print("local", join(destination, file, basename(path)))
                                # print("remote", path)
                                with open(join(destination, file, basename(path)), "wb+") as fil:
                                    conn.retrbinary("RETR %s" % path, fil.write)
                                try:
                                    dt = None
                                    if ":" in fi[-5:]:
                                        dt = datetime.strptime(
                                            datetime.now().strftime("%Y") + " ".join(fi.split()[-3:]), "%Y%b %d %H:%M")
                                    else:
                                        dt = datetime.strptime(" ".join(fi.split()[-3:]), "%b %d %Y")
                                    utime(join(destination, file, basename(path)), (dt.timestamp(), dt.timestamp()))
                                except Exception as e:
                                    print(e, path)

                        size_all = {"size": 0}
                        self.progress.configure(mode="indeterminate")
                        self.progress.start()

                        def recrse(pth, finf, rslt):
                            if finf[0] == "d":
                                makedirs(join(destination, file, basename(pth)), exist_ok=True)
                                data = {}
                                dinfo = []
                                conn.dir(pth, dinfo.append)
                                dfiles = conn.nlst(pth)
                                for f_ in sorted(dfiles, key=lambda x: (x.lower(), len(x))):
                                    fin = basename(f_)
                                    for ifo in sorted(dinfo, key=lambda x: (x.lower(), len(x))):
                                        if fin == ifo[-len(fin):]:
                                            data[fin] = ifo[:-len(fin)]
                                            dinfo.remove(ifo)
                                            break
                                for x in data.items():
                                    recrse(join(pth, x[0]), x[1], rslt)
                            elif finf[0] == "-":
                                rslt["size"] += int(finf.split()[4])

                        dat = {}
                        info = []
                        conn.dir(join(src, file), info.append)
                        files = conn.nlst(join(src, file))
                        for f in sorted(files, key=lambda x: (x.lower(), len(x))):
                            fn = basename(f)
                            for i in sorted(info, key=lambda x: (x.lower(), len(x))):
                                if fn == i[-len(fn):]:
                                    dat[fn] = i[:-len(fn)]
                                    info.remove(i)
                                    break
                        for inf in dat.items():
                            recrse(join(src, file, inf[0]), inf[1], size_all)

                        self.progress.stop()
                        self.progress.configure(mode="determinate", maximum=size_all["size"])

                        dat = {}
                        info = []
                        conn.dir(join(src, file), info.append)
                        files = conn.nlst(join(src, file))
                        for f in sorted(files, key=lambda x: (x.lower(), len(x))):
                            fn = basename(f)
                            for i in sorted(info, key=lambda x: (x.lower(), len(x))):
                                if fn == i[-len(fn):]:
                                    dat[fn] = i[:-len(fn)]
                                    info.remove(i)
                                    break
                        for inf in dat.items():
                            recurse(join(src, file, inf[0]), inf[1])

        self.is_busy = False
        if self.worker:
            self.worker.q.task_done()
            if self.worker.q.empty():
                messagebox.showinfo("DONE", "Download done!", parent=self)

    def cwd_dnl(self, event=None, ignore_item=False):
        self.progress.configure(value=0)
        if not self.connected:
            messagebox.showinfo("Connection Lost", "Please reconnect first.")

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
        else:
            p = self.path.get()
        if self.mode == "SFTP" and self.connected:
            if not p:
                channel = self.connection.session.open_session()
                channel.execute('pwd')
                channel.wait_eof()
                channel.close()
                channel.wait_closed()
                p = channel.read()[1].decode(self.enc).strip()
                self.path.set(normpath(p))
            try:
                inf = self.connection.stat(p)
            except SFTPProtocolError:
                messagebox.showerror("Path Error",
                                     "No such path or no permission to see this path.",
                                     parent=self)
                return
            if S_ISDIR(inf.permissions) != 0:
                self.path.set(normpath(p))
                self.fill(self.connection)
            else:
                if not self.is_busy and item_name:
                    destination = filedialog.askdirectory(
                        title="Choose download destination")
                    if not destination:
                        return
                    self.progress.configure(maximum=inf.filesize)
                    self.worker.add_task(
                        self.download_worker,
                        args=[
                            "/".join((self.path.get(), item_name)),
                            item_name,
                            (inf.atime, inf.mtime),
                            True,
                            destination,
                        ]
                    )
                else:
                    messagebox.showinfo("busy", "A download is already running. Try again later.")
        elif self.mode == "FTP" and self.connected:
            fd = False
            if item_name == ".." or not item or self.tree.item(item, "values")[0][0] != "-":
                try:  # Try to change into path. If we can't, then it's either a file or insufficient permissions
                    self.connection.cwd(p)
                    self.path.set(normpath(p))
                    self.fill(self.connection)
                    fd = True
                except error_perm:
                    if not item or self.tree.item(item, "values")[0][0] != "-":
                        messagebox.showerror("Path Error",
                                             "No such path or no permission to see this path.",
                                             parent=self)
                        return
                except Exception:
                    if not item or self.tree.item(item, "values")[0][0] != "-":
                        messagebox.showerror("Path Error",
                                             "No such path or no permission to see this path.",
                                             parent=self)
                        return
            if not fd:
                ts = datetime.strptime(
                    self.tree.item(item, "values")[1],
                    "%Y-%m-%d %H:%M:%S").timestamp()
                destination = filedialog.askdirectory(
                    title="Choose download destination")
                if not destination:
                    return
                self.progress.configure(maximum=self.tree.item(item, "values")[2])
                self.worker.add_task(
                    self.download_worker, args=[self.path.get(), item_name, (ts, ts), True, destination]
                )

    def fill(self, conn):
        self.tree.delete(*self.tree.get_children())
        if conn:
            if self.mode == "SFTP":
                try:
                    if not self.path.get():
                        channel = self.connection.session.open_session()
                        channel.execute('pwd')
                        channel.wait_eof()
                        channel.close()
                        channel.wait_closed()
                        self.path.set(channel.read()[1].decode(self.enc).strip())
                    with self.connection.opendir(self.path.get()) as dirh:
                        for size, buf, attrs in sorted(
                                dirh.readdir(),
                                key=(lambda f: (S_ISREG(f[2].permissions) != 0, f[1]))):
                            if buf.decode(self.enc) == "." or (self.path.get() == "/" and buf.decode(self.enc) == ".."):
                                continue
                            img = ""
                            if S_ISDIR(attrs.permissions) != 0:
                                img = self.d_img
                            elif S_ISREG(attrs.permissions) != 0:
                                img = self.f_img
                            elif S_ISLNK(attrs.permissions) != 0:
                                img = self.l_img
                            self.tree.insert(
                                "", END, text=buf.decode(self.enc),
                                values=(
                                    filemode(attrs.permissions),
                                    datetime.fromtimestamp(attrs.mtime).strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                    attrs.filesize, attrs.permissions, attrs.mtime
                                ),
                                image=img
                            )
                except SocketRecvError:
                    messagebox.showinfo("Lost connection", "The connection was lost.")
                    self.connected = False
                    self.connection = None
                    return
                except (PermissionError, SFTPProtocolError, SFTPHandleError) as e:
                    messagebox.showwarning(
                        "Permission Denied",
                        "You don't have permission to see the content of this folder."
                    )

            else:  # FTP
                if conn.pwd() != "/":
                    self.tree.insert("", END, text="..")
                if not self.path.get():
                    self.path.set(conn.pwd())

                dir_res = []
                conn.dir(dir_res.append)
                files = conn.nlst()
                data = {}
                for file in sorted(files, key=lambda x: (x.lower(), len(x))):
                    t = basename(file)
                    for fi in sorted(dir_res, key=lambda x: (x.lower(), len(x))):
                        if file in fi[-len(t):]:
                            data[t] = fi[:-len(file)]
                            dir_res.remove(fi)
                            break

                for p in sorted(data.items(), key=lambda x: (x[1][0] == "-", x[0].lower())):
                    d = p[1].split()
                    dt = None
                    if d[0][0] != "d":
                        try:
                            dt = datetime.strptime(
                                conn.voidcmd("MDTM %s" % p[0]).split()[-1],
                                "%Y%m%d%H%M%S"
                            )
                        except Exception as e:
                            print(e)
                    img = ""
                    if d[0][0] == "d":
                        img = self.d_img
                    elif d[0][0] == "-":
                        img = self.f_img
                    elif d[0][0] == "l":
                        img = self.l_img
                    self.tree.insert(
                        "", END, text=p[0],
                        values=(
                            d[0],
                            dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
                            d[4],
                            d[0][0] == "d",
                            dt.timestamp() if dt else ""
                        ),
                        image=img
                    )

            self.tree.focus_set()
            if len(self.tree.get_children("")) > 0:
                itm = self.tree.get_children("")[0]
                self.tree.see(itm)
                self.tree.focus(itm)

    def context(self, e):
        self.ctx = Menu(self, tearoff=False)
        # iid = self.tree.identify_row(e.y)
        sel = self.tree.selection()
        if len(sel) > 0:
            def download():
                destination = filedialog.askdirectory(
                    title="Choose download destination")
                if not destination:
                    return
                all_size = 0
                self.progress.configure(value=0)
                for s in sel:
                    item = self.tree.item(s)
                    isFile = item["values"][0][0] == "-"
                    if self.mode == "SFTP":
                        nfo = self.connection.stat("%s/%s" % (self.path.get(), item["text"]))
                        all_size += nfo.filesize
                        if not self.is_busy:
                            self.worker.add_task(
                                self.download_worker,
                                args=[
                                    "%s/%s" % (self.path.get(), item["text"]),
                                    item["text"], (nfo.atime, nfo.mtime),
                                    isFile,
                                    destination
                                ]
                            )
                        else:
                            messagebox.showinfo("busy",
                                                "A download is already running. Try again later.")
                    else:
                        ts = ()
                        tim = item["values"][1]
                        sz = item["values"][2]
                        if sz:
                            all_size += sz
                        if tim:
                            ts = datetime.strptime(
                                tim,
                                "%Y-%m-%d %H:%M:%S").timestamp()
                        if not self.is_busy:
                            self.worker.add_task(
                                self.download_worker,
                                args=[
                                    self.path.get(), item["text"],
                                    (ts, ts), isFile, destination
                                ]
                            )
                        else:
                            messagebox.showinfo("busy",
                                                "A download is already running. Try again later.")
                self.progress.configure(maximum=all_size)

            self.ctx.add_command(
                label="Download Selected",
                command=download
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
        def worker_(connection, mode, path, fill):
            a = AskString(self, "Create Directory",
                          "Enter a name for the new directory:")
            self.wait_window(a)
            name = a.result

            if mode == "SFTP":
                if name.strip():
                    try:
                        flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                               LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                               LIBSSH2_SFTP_S_IROTH
                        connection.mkdir(join(path, name), flgs)
                    except Exception as e:
                        print(e)
            else:
                connection.cwd(path)
                if name.strip():
                    try:
                        connection.mkd(name)
                    except Exception as e:
                        print(e)
            if name.strip():
                fill(connection)

            if self.worker:
                self.worker.q.task_done()

        self.worker.add_task(worker_, args=[
            self.mode, self.path.get(), self.fill
        ])

    def delete(self, event=None):
        def worker_(connection, mode, path_, enc, tree):
            def do_recursive(path):
                if mode == "SFTP":
                    try:
                        st = connection.stat(path).permissions
                        if S_ISREG(st) != 0:
                            connection.unlink(path)
                        elif S_ISDIR(st) != 0:
                            with connection.opendir(path) as dirh:
                                for size, buf, attrs in dirh.readdir():
                                    if buf.decode(enc) not in [".", ".."]:
                                        do_recursive(join(path, buf.decode(enc)))
                            try:
                                connection.rmdir(path)
                            except:
                                print("rmdir failed: ", path)
                                try:  # some links are recognized as folders
                                    connection.unlink(path)
                                except:
                                    print("try rm failed too: ", path)
                        elif S_ISLNK(st) != 0:
                            print("lnk: ", path)
                            try:
                                connection.unlink(path)
                            except:
                                pass
                            try:
                                connection.rmdir(path)
                            except:
                                pass
                    except:
                        print("no stat: ", path)
                        try:
                            connection.unlink(path)
                        except:
                            pass
                        try:
                            connection.rmdir(path)
                        except:
                            pass

                else:
                    try:
                        connection.delete(path)
                    except Exception as e:
                        try:
                            for obj in connection.nlst(path):
                                print(obj)
                                do_recursive(obj)
                            connection.rmd(path)
                        except Exception:
                            pass

            if mode == "SFTP":
                idx = tree.selection()
                if len(idx) > 0:
                    yesno = messagebox.askyesno(
                        "Delete Selected",
                        "Are you sure you want to delete the selected objects?"
                    )
                    if yesno:
                        for i in idx:
                            if tree.item(i, "text") in ["..", "."]:
                                continue
                            if S_ISDIR(int(tree.item(i, "values")[-2])) == 0:
                                connection.unlink(
                                    "/".join([path_.get(),
                                              tree.item(i, "text")])
                                )
                            else:
                                do_recursive("/".join([path_.get(),
                                                       tree.item(i, "text")]))
                            tree.delete(i)
            else:
                idx = tree.selection()
                if len(idx) > 0:
                    yesno = messagebox.askyesno(
                        "Delete Selected",
                        "Are you sure you want to delete the selected objects?"
                    )
                    if yesno:
                        for i in idx:
                            if tree.item(i, "text") in ["..", "."]:
                                continue
                            if tree.item(i, "values")[-2] == "True":
                                do_recursive("/".join([path_.get(),
                                                       tree.item(i, "text")]))
                            else:
                                connection.delete(
                                    "/".join([path_.get(),
                                              tree.item(i, "text")])
                                )
                            tree.delete(i)

            if self.worker:
                self.worker.q.task_done()

        self.worker.add_task(worker_, args=[
            self.mode, self.path, self.enc, self.tree
        ])

    def rename(self, event=None):
        def worker_(connection, mode, path, tree):
            idx = tree.selection()
            if len(idx) > 0:
                if tree.item(idx[0], "text") in ["..", "."]:
                    return
                a = AskString(self, "Rename",
                              "Enter new name for %s:" % tree.item(idx[0], "text"),
                              initial_value=tree.item(idx[0], "text"))
                self.wait_window(a)
                name = a.result

                if mode == "SFTP":
                    if name and name.strip():
                        try:
                            connection.rename(
                                join(path, tree.item(idx[0], "text")),
                                join(path, name))
                            tree.item(idx[0], text=name)
                        except Exception as e:
                            print(e)
                else:
                    if name.strip():
                        connection.cwd(path)
                        try:
                            connection.rename(tree.item(idx[0], "text"),
                                              name)
                            tree.item(idx[0], text=name)
                        except Exception as e:
                            print(e)

            if self.worker:
                self.worker.q.task_done()

        self.worker.add_task(worker_, args=[
            self.mode, self.path.get(), self.tree
        ])

    def upload_file(self):
        def worker_(conn, rt):
            size_all = 0
            files = filedialog.askopenfilenames(title="Choose files to upload",
                                                parent=rt)
            a = AskString(self, "Choose destination",
                          "Choose upload destination",
                          initial_value=rt.path.get())
            self.wait_window(a)
            dest = a.result

            if files:
                self.progress.configure(mode="indeterminate", value=0)
                self.progress.start()
                for f in files:
                    size_all += getsize(f)
                self.progress.stop()
                self.progress.configure(mode="determinate", maximum=size_all)

            if files and len(files) > 0 and dest:
                if rt.mode == "SFTP":
                    rt.is_busy = True
                    for file in files:
                        fifo = stat(file)

                        # chan = conn.session.scp_send64(
                        #     "%s/%s" % (dest.strip(), basename(file)),
                        #     fifo.st_mode & 0o777,
                        #     fifo.st_size,
                        #     fifo.st_mtime, fifo.st_atime)
                        mode = LIBSSH2_SFTP_S_IRUSR | \
                               LIBSSH2_SFTP_S_IWUSR | \
                               LIBSSH2_SFTP_S_IRGRP | \
                               LIBSSH2_SFTP_S_IROTH
                        f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
                        with open(file, 'rb') as lofi:
                            with conn.open("%s/%s" % (dest.strip(), basename(file)), f_flags, mode) as remfi:
                                while True:
                                    data = lofi.read(10*1024*1024)
                                    if not data:
                                        break
                                    else:
                                        _, sz = remfi.write(data)
                                        self.progress.step(sz)
                                attr = SFTPAttributes(fifo)
                                # attr.filesize = fifo.st_size
                                # print(file, datetime.fromtimestamp(fifo.st_mtime))
                                # attr.atime = fifo.st_atime
                                # attr.mtime = fifo.st_mtime
                                # attr.permissions = fifo.st_mode
                                # attr.gid = fifo.st_gid
                                # attr.uid = fifo.st_uid
                                remfi.fsetstat(attr)
                        t = conn.stat("%s/%s" % (dest.strip(), basename(file)))
                        print(datetime.fromtimestamp(t.atime), datetime.fromtimestamp(t.mtime))
                else:
                    rt.is_busy = True
                    # conn.cwd(dest)
                    for file in files:
                        try:
                            def handl(blk):
                                self.progress.step(len(blk))
                            with open(file, "rb") as f:
                                conn.storbinary(
                                    "STOR %s" % join(dest, basename(file)), f, callback=handl
                                )
                            conn.voidcmd("MFMT %s %s" % (
                                datetime.fromtimestamp(
                                    getmtime(file)
                                ).strftime("%Y%m%d%H%M%S"),
                                file
                            ))
                        except Exception as e:
                            print(e)
            rt.fill(conn)
            rt.is_busy = False

            if self.worker:
                self.worker.q.task_done()
                if self.worker.q.empty():
                    messagebox.showinfo("DONE", "Upload done!", parent=rt)

        self.worker.add_task(worker_, args=[self, ])

    def upload_folder(self):
        def worker_(conn, rt):
            size_all = {"size": 0}
            folder = filedialog.askdirectory(
                title="Choose folder to upload", parent=rt
            )

            a = AskString(self, "Choose upload destination",
                          "Input upload destination path",
                          initial_value=rt.path.get())
            self.wait_window(a)
            dest = a.result

            if folder:
                self.progress.configure(mode="indeterminate", value=0)
                self.progress.start()

                def recrse(pth, rslt):
                    for f in listdir(pth):
                        fp = join(pth, f)
                        if isfile(fp) and not islink(fp):
                            rslt["size"] += getsize(fp)
                        elif isdir(fp) and not islink(fp):
                            recrse(fp, rslt)
                recrse(folder, size_all)
                self.progress.stop()
                self.progress.configure(mode="determinate", maximum=size_all["size"])
                print(size_all)

            def recurse(destination, target):
                if rt.mode == "SFTP":
                    if islink(target):
                        return
                    elif isdir(target):
                        try:
                            flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                                   LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                                   LIBSSH2_SFTP_S_IROTH
                            conn.mkdir("%s/%s" % (destination, basename(target)), flgs)
                            for f in listdir(target):
                                recurse("%s/%s" % (destination, basename(target)),
                                        "%s/%s" % (target, basename(f)))
                        except Exception as e:
                            print(target, e)
                    elif isfile(target):
                        fifo = stat(target)
                        mode = LIBSSH2_SFTP_S_IRUSR | \
                               LIBSSH2_SFTP_S_IWUSR | \
                               LIBSSH2_SFTP_S_IRGRP | \
                               LIBSSH2_SFTP_S_IROTH
                        f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
                        with open(target, 'rb') as lofi:
                            # print("target", target)
                            # print("dest", "%s/%s" % (destination.strip(), basename(target)))
                            with conn.open(
                                    "%s/%s" % (destination.strip(), basename(target)),
                                    f_flags, mode) as remfi:
                                for data in lofi:
                                    remfi.write(data)
                                    self.progress.step(len(data))
                                attr = SFTPAttributes(fifo)
                                # attr.filesize = fifo.st_size
                                # print(file, datetime.fromtimestamp(fifo.st_mtime))
                                # attr.atime = fifo.st_atime
                                # attr.mtime = fifo.st_mtime
                                # attr.permissions = fifo.st_mode
                                # attr.gid = fifo.st_gid
                                # attr.uid = fifo.st_uid
                                remfi.fsetstat(attr)
                        # t = conn.stat(
                        #     "%s/%s" % (destination.strip(), basename(target)))
                        # print(datetime.fromtimestamp(t.atime),
                        #       datetime.fromtimestamp(t.mtime))
                else:
                    # conn.cwd(rt.path.get())
                    if islink(target):
                        return
                    elif isdir(target):
                        conn.mkd(
                            "%s/%s" % (destination, basename(target))
                        )
                        for f in listdir(target):
                            recurse("%s/%s" % (destination, basename(target)),
                                    "%s/%s" % (target, basename(f)))
                    elif isfile(target):
                        try:
                            def handl(blk):
                                self.progress.step(len(blk))
                            with open(target, "rb") as f:
                                conn.storbinary(
                                    "STOR %s/%s" % (destination, basename(target)),
                                    f, callback=handl
                                )
                            conn.voidcmd(
                                "MDTM %s %s" % (
                                    datetime.fromtimestamp(
                                        getmtime(target)
                                    ).strftime("%Y%m%d%H%M%S"),
                                    "%s/%s" % (destination, basename(target))
                                )
                            )
                        except Exception as e:
                            print(e)

            if folder and dest:
                rt.is_busy = True
                if rt.mode == "SFTP":
                    try:
                        p = rt.path.get()
                        if p in dest:
                            tmp = dest[len(p) + 1:]  # +1 to remove slash
                        for fo in tmp.split("/"):
                            if fo:
                                # conn.mkdir(fo, encoding=rt.enc)
                                # conn.chdir(fo, encoding=rt.enc)
                                flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                                       LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                                       LIBSSH2_SFTP_S_IROTH
                                conn.mkdir(fo, flgs)
                        rt.path.set(normpath("%s/%s" % (p, fo)))
                    except Exception as e:
                        pass
                    if not isfile(folder):
                        try:
                            # conn.mkdir(basename(folder))
                            flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                                   LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                                   LIBSSH2_SFTP_S_IROTH
                            conn.mkdir("%s/%s" % (rt.path.get(), basename(folder)), flgs)
                        except Exception as e:
                            pass
                else:
                    conn.cwd(rt.path.get())
                    try:
                        p = rt.path.get()
                        tmp = ""
                        if p in dest:
                            tmp = dest[len(p) + 1:]  # +1 to remove slash
                        ctmp = p
                        for fo in tmp.split("/"):
                            try:
                                if fo:
                                    conn.mkd("%s/%s" % (ctmp, fo))
                                    ctmp += "/" + fo
                            except Exception as e:
                                print(ctmp, e)
                        conn.mkd(
                            "%s/%s" % (dest, basename(folder))
                        )
                        # rt.path.set(conn.pwd())
                    except Exception as e:
                        print("mkdir orig2 err:", e)
                for f_ in listdir(folder):
                    recurse(normpath("%s/%s" % (dest, basename(folder))),
                            normpath("%s/%s" % (folder, basename(f_))))

                self.fill(conn)
                rt.is_busy = False

                if self.worker:
                    self.worker.q.task_done()
                    if self.worker.q.empty():
                        messagebox.showinfo("DONE", "Upload done!", parent=rt)

        self.worker.add_task(worker_, args=[self, ])

    def keep_alive(self):
        if not self.keep_alive_timer_running and self.connected:
            t = Timer(10, self.keep_alive_worker)
            t.setDaemon(True)
            t.start()

    def keep_alive_worker(self):
        if self.connected:
            if self.mode == "SFTP":
                if not self.is_busy:
                    try:
                        transport = self.connection.get_transport()
                        transport.send_ignore()
                    except EOFError:
                        self.connected = False

            else:  # FTP
                if not self.is_busy:
                    try:
                        self.connection.voidcmd("NOOP")
                    except Exception:
                        self.connected = False

            if not self.connected:
                self.connect_btn["text"] = "Connect"

        self.keep_alive_timer_running = False
        if self.connected:
            self.keep_alive()

    def connect(self):
        def worker(self):
            connection = None

            if self.profileCB.get() == "please select a profile":
                text = "Please select a profile to connect to."
                if len(self.profileCB["values"]) == 0:
                    text = "Please create a profile first."
                messagebox.showinfo("No connection data", text)

            if self.mode == "SFTP":
                import os
                from ssh2.session import LIBSSH2_HOSTKEY_HASH_SHA1, \
                    LIBSSH2_HOSTKEY_TYPE_RSA
                from ssh2.knownhost import LIBSSH2_KNOWNHOST_TYPE_PLAIN, \
                    LIBSSH2_KNOWNHOST_KEYENC_RAW, LIBSSH2_KNOWNHOST_KEY_SSHRSA, LIBSSH2_KNOWNHOST_KEY_SSHDSS
                if not self.connected:
                    try:
                        sock = socket(AF_INET, SOCK_STREAM)
                        sock.settimeout(10)
                        sock.connect((self.connectionCB.get(), self.port))
                        cli = Session()
                        cli.set_timeout(15000)
                        cli.handshake(sock)

                        cli.userauth_password(self.nameE.get(), self.password)
                        sftp = cli.sftp_init()

                        cli.set_timeout(0)

                        connection = sftp
                    except Timeout:
                        messagebox.showerror("Connection Error", "Connection timeout on login.")
                    except Exception as e:
                        messagebox.showerror("Connection Error", str(e))
                        return

                else:
                    try:
                        self.connection.session.disconnect()
                        self.worker.quit()
                        self.progress.configure(value=0)
                        self.worker = None

                        prof = self.conf["profiles"][self.profileCB.get()]
                        if self.save_last_path.get():
                            prof["save_last_path"] = True
                            prof["path"] = self.path.get()
                        else:
                            prof["save_last_path"] = False
                    except Exception as e:
                        pass
                    finally:
                        self.connected = False

            else:  # FTP
                if not self.connected:
                    try:
                        ftp = FTP()
                        ftp.encoding = self.enc
                        ftp.connect(self.connectionCB.get(), self.port, 10)
                        ftp.login(self.nameE.get(), self.password)

                        connection = ftp
                    except Exception as e:
                        print(e)
                        return

                    try:
                        connection.cwd(self.path.get())
                    except error_perm:
                        self.connected = False
                        connection.quit()
                else:
                    try:
                        self.connection.close()
                        self.worker.quit()
                        self.progress.configure(value=0)
                        self.worker = None

                        prof = self.conf["profiles"][self.profileCB.get()]
                        if self.save_last_path.get():
                            prof["save_last_path"] = True
                            prof["path"] = self.path.get()
                        else:
                            prof["save_last_path"] = False
                    except Exception as e:
                        pass
                    finally:
                        self.connected = False

            self.connection = connection
            if connection:
                self.fill(connection)
                self.connected = True
                self.worker = ThreadWork(
                    self.mode,
                    self.connectionCB.get(),
                    self.port,
                    self.nameE.get(),
                    self.password,
                    self.enc
                )

            self.connect_btn["text"] = "Connect" if not self.connected else "Disconnect"

        singleShot(worker, [self, ])

    def destroy(self):
        self.conf["current_profile"] = self.profileCB.get()
        Config.save_file(self.conf)
        if self.worker:
            self.worker.quit()
        super().destroy()


if __name__ == "__main__":
    MainView()
    exit()
