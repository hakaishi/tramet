#!/usr/bin/env python
# -*- encoding=utf8 -*-

from sys import exit
from os import listdir, makedirs, utime, stat
from os.path import exists, join, basename, getmtime, getatime, isdir, normpath,\
    dirname, abspath, isfile, islink
from stat import S_ISDIR, S_ISLNK, S_ISREG, filemode
from datetime import datetime
from threading import Timer, Thread
from queue import Queue

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import filedialog, messagebox, simpledialog

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ssh2.sftp import *
from ssh2.sftp_handle import SFTPAttributes
from ftplib import FTP, error_perm

from Config import Config


class MainView(Tk):
    def __init__(self):
        super().__init__()

        self.f_img = PhotoImage(file="file.png")
        self.d_img = PhotoImage(file="folder.png")
        self.l_img = PhotoImage(file="link.png")

        self.geometry("500x400")
        self.minsize(500, 400)

        self.wm_title("Tramet")

        self.conf = Config.load_file()
        self.q = Queue()

        self.enc = "utf-8"
        self.path = "/"
        self.mode = "SFTP"
        self.password = ""
        self.port = 22
        self.connection = None
        self.connected = False
        self.keep_alive_timer_running = False
        self.is_busy = False
        
        self.menubar = Menu(self)
        self.configure(menu=self.menubar)
        
        self.filemenu = Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.filemenu.add_command(label="Profiles", command=self.open_profiles)
        self.filemenu.add_command(label="Exit", command=self.destroy)
        self.menubar.add_command(label="Search", command=self.search)
        
        frame = Frame(self)

        Label(frame, text="profile:").grid(row=0, column=0, sticky=W)
        self.profileCB = Combobox(frame, state="readonly", values=list(self.conf.keys()))
        self.profileCB.bind("<<ComboboxSelected>>", self.set_profile)
        self.profileCB.grid(row=0, column=1, sticky=EW, columnspan=3)

        Label(frame, text="host:").grid(row=1, column=0, sticky=W)
        self.connectionCB = Combobox(frame, state="disabled", values=list(
            set(map(lambda x: x[1]["host"], self.conf.items()))
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

        self.connect_btn = Button(frame, text="load", command=self.connect)
        self.connect_btn.grid(row=4, column=0, columnspan=4, sticky=EW, pady=10)

        frame.pack(fill=X, expand=True)
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
        self.tree.bind("<Button-1>", self.selection)
        self.tree.bind('<FocusIn>', self.on_get_focus)
        self.tree.bind("<Button-3>", self.context)

        scrollbar.config(command=self.tree.yview)

        tree_frame.pack(fill=BOTH, expand=True)

        self.ctx = None
        
        Sizegrip(self).pack(side=RIGHT)

        self.mainloop()

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
        if p:
            prof = self.conf[p]
            self.connectionCB.set(prof["host"])
            self.port = prof["port"]
            self.name.set(prof["user"])
            self.pathE.delete(0, END)
            self.pathE.insert(END, prof["path"])
            self.enc = prof["encoding"]
            self.mode = prof["mode"]
            self.modeL["text"] = prof["mode"]
            self.password = prof["password"]

    def open_profiles(self):
        Config(self)

    def selection(self, e=None):
        if self.ctx:
            self.ctx.destroy()
            self.ctx = None

    def search(self, event=None):  # todo
        messagebox.showinfo("Not yet", "Work in progress", parent=self)

    def download_worker(self, src, file, ts, isFile=True):
        if isFile:
            folder = filedialog.askdirectory(
                title="Choose download destination")
            if folder:
                overwrite = True
                if exists(join(folder, file)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing file?",
                        "A file with the same name already exists. Do you want to override it?",
                        parent=self)
                if overwrite:
                    self.is_busy = True
                    if self.mode == "SFTP":
                        # print(src)
                        try:
                            res = self.connection.session.scp_recv2(src)
                            if res:
                                with open(join(folder, file), "wb+") as f:
                                    size = 0
                                    while True:
                                        siz, tbuff = res[0].read()
                                        if siz < 0:
                                            print("error code:", siz)
                                            res[0].close()
                                            break
                                        size += siz
                                        if size > res[1].st_size:
                                            f.write(tbuff[:(size - res[1].st_size)])
                                        else:
                                            f.write(tbuff)
                                        if size >= res[1].st_size:
                                            res[0].close()
                                            break
                                utime(join(folder, file), (res[1].st_atime, res[1].st_mtime))
                        except Exception as e:
                            print("error: ", e)
                        print("done")
                        # self.connection.get(src, join(folder, file),
                        #                     encoding=self.enc, errors="replace")
                        # utime(join(folder, file), ts)

                    else:
                        with open(join(folder, file), "wb+") as f:
                            self.connection.retrbinary("RETR %s" % src, f.write)
                        utime(join(folder, file), ts)
        else:
            folder = filedialog.askdirectory(
                title="Choose download destination")
            if folder:
                overwrite = True
                if exists(join(folder, file)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing files?",
                        "A folder with the same name already exists. Do you want to override all contained files?",
                        parent=self)
                else:
                    makedirs(join(folder, file), exist_ok=True)
                if overwrite:
                    self.is_busy = True

                    if self.mode == "SFTP":
                        def recurse(orig, path, fi):
                            if S_ISDIR(fi[1].permissions) != 0:
                                makedirs(path, exist_ok=True)
                                with self.connection.opendir(orig) as dirh_:
                                    for size_, buf_, attrs_ in dirh_.readdir():
                                        o_ = buf_.decode(self.enc)
                                        if o_ not in [".", ".."]:
                                            recurse(join(orig, o_), join(path, o_), (o_, attrs_))
                            elif S_ISREG(fi[1].permissions) != 0:
                                res_ = self.connection.session.scp_recv2(orig)
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

                                # self.connection.get(
                                #     join(path, fi.filename),
                                #     join(folder, path, fi.filename),
                                #     encoding=self.enc
                                # )
                                # utime(join(path, fi.filename),
                                #       (fi.st_atime, fi.st_mtime)
                                # )

                        # for obj in self.connection.listdir_attr(
                        #         src, encoding=self.enc
                        # ):
                        #     recurse(src, obj)
                        with self.connection.opendir(src) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                o = buf.decode(self.enc)
                                if o not in [".", ".."]:
                                    recurse(join(src, o), join(folder, file, o), (o, attrs))
                        print("done")
                    else:
                        def recurse(path, fi):
                            if fi[0] == "d":
                                makedirs(join(folder, path), exist_ok=True)
                                data = {}
                                dinfo = []
                                self.connection.dir(path, dinfo.append)
                                dfiles = self.connection.nlst(path)
                                for f_ in sorted(dfiles, key=len):
                                    fin = basename(f_)
                                    for ifo in sorted(dinfo, key=len):
                                        if fin == ifo[-len(fin):]:
                                            data[fin] = ifo[:-len(fin)]
                                            break
                                for x in data.items():
                                    recurse(join(path, x[0]), x[1])
                            elif fi[0] == "-":
                                with open(join(folder, path), "wb+") as fil:
                                    self.connection.retrbinary("RETR %s" % path, fil.write)
                                try:
                                    dt = None
                                    if ":" in fi[-5:]:
                                        dt = datetime.strptime(datetime.now().strftime("%Y")+" ".join(fi.split()[-3:]), "%Y%b %d %H:%M")
                                    else:
                                        dt = datetime.strptime(" ".join(fi.split()[-3:]), "%b %d %Y")
                                    utime(join(folder, path), (dt.timestamp(), dt.timestamp()))
                                except Exception as e:
                                    print(e, path)

                        dat = {}
                        info = []
                        self.connection.dir(src, info.append)
                        files = self.connection.nlst(src)
                        for f in sorted(files, key=len):
                            fn = basename(f)
                            for i in sorted(info, key=len):
                                if fn == i[-len(fn):]:
                                    dat[fn] = i[:-len(fn)]
                                    break
                        for inf in dat.items():
                            recurse(join(src, inf[0]), inf[1])

        self.is_busy = False

    def cwd_dnl(self, event=None):
        self.selection()

        item = ""
        if str(event.type) == "ButtonPress":
            item = self.tree.identify('item', event.x, event.y)
        elif event.keysym == "Return":
            sel = self.tree.selection()
            if len(sel) > 0:
                item = self.tree.selection()[0]

        p = ""
        item_name = self.tree.item(item, "text")
        if item_name == "..":
            p += "/".join(self.path.get().split("/")[:-1]) or "/"
        else:
            p += self.path.get()
            p = "/".join(((p if p != "/" else ""), item_name))
        if self.mode == "SFTP" and self.connected:
            inf = self.connection.stat(p)
            if S_ISDIR(inf.permissions) != 0:
                self.pathE.delete(0, END)
                self.pathE.insert(END, p)
                self.fill(self.connection)
            else:
                if not self.is_busy:
                    Thread(target=self.download_worker,
                           args=["/".join((self.path.get(), item_name)),
                                 item_name, (inf.atime, inf.mtime)],
                           daemon=True).start()
                else:
                    messagebox.showinfo("busy", "A download is already running. Try again later.")
        elif self.mode == "FTP" and self.connected:
            fd = False
            if item_name == ".." or self.tree.item(item, "values")[0][0] != "-":
                try:
                    self.connection.cwd(p)
                    self.pathE.delete(0, END)
                    self.pathE.insert(END, p)
                    self.fill(self.connection)
                    fd = True
                except Exception:
                    pass
            if not fd:
                ts = datetime.strptime(
                                 self.tree.item(item, "values")[1],
                                 "%Y-%m-%d %H:%M:%S").timestamp()
                Thread(target=self.download_worker,
                       args=[item_name, item_name, (ts, ts)],
                       daemon=True).start()

    def fill(self, conn):
        self.tree.delete(*self.tree.get_children())
        if self.mode == "SFTP":
            try:
                with self.connection.opendir(self.path.get()) as dirh:
                    for size, buf, attrs in sorted(
                            dirh.readdir(),
                            key=(lambda f: (S_ISREG(f[2].permissions) != 0, f[1]))):
                        if buf.decode(self.enc) == ".":
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
            except PermissionError:
                messagebox.showwarning(
                    "Permission Denied",
                    "You don't have permission to see the content of this folder."
                )

        else:  # FTP
            if conn.pwd() != "/":
                self.tree.insert("", END, text="..")

            dir_res = []
            conn.dir(dir_res.append)
            files = conn.nlst()
            data = {}
            for file in files:
                for fi in dir_res:
                    if file in fi:
                        data[file] = fi[:-len(file)]

            for p in sorted(data.items(), key=lambda x: (x[1][0] == "-", x[0])):
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
        self.tree.focus(self.tree.get_children("")[0])

    def context(self, e):
        self.ctx = Menu(self, tearoff=False)
        # iid = self.tree.identify_row(e.y)
        sel = self.tree.selection()
        if len(sel) > 0:
            def download():
                s = sel[0]  # TODO: queuing
                # for s in sel:
                item = self.tree.item(s)
                isFile = item["values"][0][0] == "-"
                if self.mode == "SFTP":
                    nfo = self.connection.stat("%s/%s" % (self.path.get(), item["text"]))
                    if not self.is_busy:
                        t = Thread(target=self.download_worker, args=[
                            "%s/%s" % (self.path.get(), item["text"]), item["text"], (nfo.atime, nfo.mtime),
                            isFile
                        ], daemon=True)
                        t.start()
                    else:
                        messagebox.showinfo("busy",
                                            "A download is already running. Try again later.")
                else:
                    ts = ()
                    tim = item["values"][1]
                    if tim:
                        ts = datetime.strptime(
                                     tim,
                                     "%Y-%m-%d %H:%M:%S").timestamp()
                    if not self.is_busy:
                        t = Thread(target=self.download_worker, args=[
                            self.path.get(), item["text"],
                            (ts, ts), isFile
                        ], daemon=True)
                        t.start()
                    else:
                        messagebox.showinfo("busy",
                                            "A download is already running. Try again later.")

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

    # def download_folder(self, folder):
    #     if not self.is_busy:
    #         t = Thread(target=self.download_worker, args=[
    #             folder, folder,
    #             None, False
    #         ], daemon=True)
    #         t.start()
    #     else:
    #         messagebox.showinfo("busy",
    #                             "A download is already running. Try again later.")

    def mkdir(self):
        name = simpledialog.askstring("Create Directory",
                                      "Enter a name for the new directory:")
        if self.mode == "SFTP":
            if name.strip():
                try:
                    flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                           LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                           LIBSSH2_SFTP_S_IROTH
                    self.connection.mkdir(join(self.path.get(), name), flgs)
                except Exception as e:
                    print(e)
        else:
            if name.strip():
                try:
                    self.connection.mkd(name)
                except Exception as e:
                    print(e)
        self.fill(self.connection)

    def delete(self):
        def do_recursive(path):
            if self.mode == "SFTP":
                try:
                    st = self.connection.stat(path).permissions
                    if S_ISREG(st) != 0:
                        self.connection.unlink(path)
                    elif S_ISDIR(st) != 0:
                        with self.connection.opendir(path) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                if buf.decode(self.enc) not in [".", ".."]:
                                    do_recursive(join(path, buf.decode(self.enc)))
                        try:
                            self.connection.rmdir(path)
                        except:
                            print("rmdir failed: ", path)
                            try:  # some links are recognized as folders
                                self.connection.unlink(path)
                            except:
                                print("try rm failed too: ", path)
                    elif S_ISLNK(st) != 0:
                        print("lnk: ", path)
                        try:
                            self.connection.unlink(path)
                        except:
                            pass
                        try:
                            self.connection.rmdir(path)
                        except:
                            pass
                except:
                    print("no stat: ", path)
                    try:
                        self.connection.unlink(path)
                    except:
                        pass
                    try:
                        self.connection.rmdir(path)
                    except:
                        pass

            else:
                try:
                    self.connection.delete(path)
                except Exception as e:
                    try:
                        for obj in self.connection.nlst(path):
                            print(obj)
                            do_recursive(obj)
                        self.connection.rmd(path)
                    except Exception:
                        pass

        if self.mode == "SFTP":
            idx = self.tree.selection()
            if len(idx) > 0:
                yesno = messagebox.askyesno(
                    "Delete Selected",
                    "Are you sure you want to delete the selected objects?"
                )
                if yesno:
                    for i in idx:
                        if S_ISDIR(int(self.tree.item(i, "values")[-2])) == 0:
                            self.connection.unlink(
                                "/".join([self.path.get(),
                                          self.tree.item(i, "text")])
                            )
                        else:
                            do_recursive("/".join([self.path.get(),
                                                   self.tree.item(i, "text")]))
                        self.tree.delete(i)
        else:
            idx = self.tree.selection()
            if len(idx) > 0:
                yesno = messagebox.askyesno(
                    "Delete Selected",
                    "Are you sure you want to delete the selected objects?"
                )
                if yesno:
                    for i in idx:
                        if self.tree.item(i, "values")[-2] == "True":
                            do_recursive("/".join([self.path.get(),
                                                   self.tree.item(i, "text")]))
                        else:
                            self.connection.delete(
                                "/".join([self.path.get(),
                                          self.tree.item(i, "text")])
                            )
                        self.tree.delete(i)

    def rename(self):
        idx = self.tree.selection()
        if len(idx) > 0:
            name = simpledialog.askstring("Rename", "Enter new name for %s:"
                                          % self.tree.item(idx[0], "text"),
                                          initialvalue=self.tree.item(idx[0], "text"))
            if self.mode == "SFTP":
                if name and name.strip():
                    try:
                        self.connection.rename(
                            join(self.path.get(), self.tree.item(idx[0], "text")),
                            join(self.path.get(), name))
                        self.tree.item(idx[0], text=name)
                    except Exception as e:
                        print(e)
            else:
                if name.strip():
                    try:
                        self.connection.rename(self.tree.item(idx[0], "text"),
                                               name)
                        self.tree.item(idx[0], text=name)
                    except Exception as e:
                        print(e)

    def upload_file(self):
        files = filedialog.askopenfilenames(title="Choose files to upload",
                                            parent=self)
        dest = simpledialog.askstring(
            title="Choose destination", prompt="Choose upload destination",
            parent=self, initialvalue=self.path.get()
        )
        if files and len(files) > 0 and dest:
            if self.mode == "SFTP":
                self.is_busy = True
                for file in files:
                    # tm = getmtime(file)
                    # ta = getatime(file)
                    # tgt = "%s/%s" % (dest.strip(), basename(file))
                    # self.connection.put(file, tgt, encoding=self.enc)
                    # self.connection.utime(tgt, (ta, tm), encoding=self.enc)
                    fifo = stat(file)

                    # chan = self.connection.session.scp_send64(
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
                        with self.connection.open("%s/%s" % (dest.strip(), basename(file)), f_flags, mode) as remfi:
                            for data in lofi:
                                remfi.write(data)
                            attr = SFTPAttributes(fifo)
                            # attr.filesize = fifo.st_size
                            # print(file, datetime.fromtimestamp(fifo.st_mtime))
                            # attr.atime = fifo.st_atime
                            # attr.mtime = fifo.st_mtime
                            # attr.permissions = fifo.st_mode
                            # attr.gid = fifo.st_gid
                            # attr.uid = fifo.st_uid
                            remfi.fsetstat(attr)
                    t = self.connection.stat("%s/%s" % (dest.strip(), basename(file)))
                    print(datetime.fromtimestamp(t.atime), datetime.fromtimestamp(t.mtime))
            else:
                self.is_busy = True
                for file in files:
                    try:
                        with open(file, "rb") as f:
                            self.connection.storbinary(
                                "STOR %s" % basename(file), f
                            )
                        self.connection.voidcmd("MFMT %s %s" % (
                            datetime.fromtimestamp(
                                getmtime(file)
                            ).strftime("%Y%m%d%H%M%S"),
                            file
                        ))
                    except Exception as e:
                        print(e)
        self.fill(self.connection)
        self.is_busy = False

    def upload_folder(self):
        folder = filedialog.askdirectory(
            title="Choose folder to upload", parent=self
        )
        dest = simpledialog.askstring(
            title="Choose upload destination",
            prompt="Input upload destination path",
            parent=self,
            initialvalue=self.path.get()
        )

        def recurse(destination, target):
            if self.mode == "SFTP":
                if islink(target):
                    return
                elif isdir(target):
                    try:
                        # self.connection.mkdir(
                        #     "%s/%s" % (destination, basename(target)),
                        #     encoding=self.enc
                        # )
                        flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                               LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                               LIBSSH2_SFTP_S_IROTH
                        self.connection.mkdir("%s/%s" % (destination, basename(target)), flgs)
                        for f in listdir(target):
                            recurse("%s/%s" % (destination, basename(target)),
                                    "%s/%s" % (target, basename(f)))
                    except Exception as e:
                        print(target, e)
                elif isfile(target):
                    # tm = getmtime(target)
                    # ta = getatime(target)
                    # self.connection.put(
                    #     target, "%s/%s" % (destination, basename(target)),
                    #     encoding=self.enc
                    # )
                    # self.connection.utime(
                    #     "%s/%s" % (destination, basename(target)), (ta, tm),
                    #     encoding=self.enc
                    # )
                    fifo = stat(target)
                    mode = LIBSSH2_SFTP_S_IRUSR | \
                           LIBSSH2_SFTP_S_IWUSR | \
                           LIBSSH2_SFTP_S_IRGRP | \
                           LIBSSH2_SFTP_S_IROTH
                    f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
                    with open(target, 'rb') as lofi:
                        # print("target", target)
                        # print("dest", "%s/%s" % (destination.strip(), basename(target)))
                        with self.connection.open(
                                "%s/%s" % (destination.strip(), basename(target)),
                                f_flags, mode) as remfi:
                            for data in lofi:
                                remfi.write(data)
                            attr = SFTPAttributes(fifo)
                            # attr.filesize = fifo.st_size
                            # print(file, datetime.fromtimestamp(fifo.st_mtime))
                            # attr.atime = fifo.st_atime
                            # attr.mtime = fifo.st_mtime
                            # attr.permissions = fifo.st_mode
                            # attr.gid = fifo.st_gid
                            # attr.uid = fifo.st_uid
                            remfi.fsetstat(attr)
                    # t = self.connection.stat(
                    #     "%s/%s" % (destination.strip(), basename(target)))
                    # print(datetime.fromtimestamp(t.atime),
                    #       datetime.fromtimestamp(t.mtime))
            else:
                if islink(target):
                    return
                elif isdir(target):
                    self.connection.mkd(
                        "%s/%s" % (destination, basename(target))
                    )
                    for f in listdir(target):
                        recurse("%s/%s" % (destination, basename(target)),
                                "%s/%s" % (target, basename(f)))
                elif isfile(target):
                    try:
                        with open(target, "rb") as f:
                            self.connection.storbinary(
                                "STOR %s/%s" % (destination, basename(target)),
                                f
                            )
                        self.connection.voidcmd(
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
            self.is_busy = True
            if self.mode == "SFTP":
                try:
                    p = self.path.get()
                    if p in dest:
                        tmp = dest[len(p)+1:]  # +1 to remove slash
                    for fo in tmp.split("/"):
                        if fo:
                            # self.connection.mkdir(fo, encoding=self.enc)
                            # self.connection.chdir(fo, encoding=self.enc)
                            flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                                   LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                                   LIBSSH2_SFTP_S_IROTH
                            self.connection.mkdir(fo, flgs)
                    self.path.set("%s/%s" % (p, fo))
                except Exception as e:
                    pass
                if not isfile(folder):
                    try:
                        # self.connection.mkdir(basename(folder))
                        flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                               LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                               LIBSSH2_SFTP_S_IROTH
                        self.connection.mkdir("%s/%s" % (self.path.get(), basename(folder)), flgs)
                    except Exception as e:
                        pass
            else:
                try:
                    p = self.path.get()
                    if p in dest:
                        tmp = dest[len(p) + 1:]  # +1 to remove slash
                    for fo in tmp.split("/"):
                        if fo:
                            self.connection.mkd(dest)
                            self.connection.mkd(
                                "%s/%s" % (dest, basename(folder))
                            )
                    self.path.set(self.connection.pwd())
                except Exception as e:
                    print("mkdir orig2 err:", e)
                if not isfile(folder):
                    try:
                        self.connection.mkd(basename(folder))
                    except Exception as e:
                        pass
            for f_ in listdir(folder):
                recurse(normpath("%s/%s" % (dest, basename(folder))),
                        normpath("%s/%s" % (folder, basename(f_))))

            self.fill(self.connection)
            self.is_busy = False

    def keep_alive(self):
        if not self.keep_alive_timer_running:
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
        connection = None

        if self.mode == "SFTP":
            import os
            from ssh2.session import LIBSSH2_HOSTKEY_HASH_SHA1, \
                LIBSSH2_HOSTKEY_TYPE_RSA
            from ssh2.knownhost import LIBSSH2_KNOWNHOST_TYPE_PLAIN, \
                LIBSSH2_KNOWNHOST_KEYENC_RAW, LIBSSH2_KNOWNHOST_KEY_SSHRSA, LIBSSH2_KNOWNHOST_KEY_SSHDSS
            if not self.connected:
                try:
                    sock = socket(AF_INET, SOCK_STREAM)
                    sock.connect((self.connectionCB.get(), self.port))
                    sock.settimeout(3)
                    cli = Session()
                    cli.handshake(sock)

                    cli.userauth_password(self.nameE.get(), self.password)
                    sftp = cli.sftp_init()

                    connection = sftp
                except Exception as e:
                    print(e)
                    return

            else:
                try:
                    self.connection.session.disconnect()
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
                except Exception as e:
                    pass
                finally:
                    self.connected = False

        self.connection = connection
        if connection:
            self.fill(connection)
            self.connected = True

        self.connect_btn["text"] = "Connect" if not self.connected else "Disconnect"

        return connection


if __name__ == "__main__":
    MainView()
    exit()
