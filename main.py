#!/usr/bin/env python
# -*- encoding=utf8 -*-

from sys import exit
from os import listdir
from os.path import exists, join, basename, getmtime, getatime, isdir, normpath, dirname, abspath, isfile, islink
from stat import S_ISDIR, S_ISLNK, S_ISREG, filemode
from datetime import datetime
from threading import Timer, Thread

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import filedialog, messagebox, simpledialog

from paramiko import SSHClient, AutoAddPolicy
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

        self.conf = Config.load_file()

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
        self.profileCB = Combobox(frame, values=list(self.conf.keys()))
        self.profileCB.bind("<<ComboboxSelected>>", self.set_profile)
        self.profileCB.grid(row=0, column=1, sticky=EW, columnspan=3)

        Label(frame, text="host:").grid(row=1, column=0, sticky=W)
        self.connectionCB = Combobox(frame, values=list(set(map(lambda x: x[1]["host"], self.conf.items()))))
        self.connectionCB.grid(row=1, column=1, sticky=EW, columnspan=1)

        Label(frame, text="mode:").grid(row=1, column=2, sticky=W, padx=3)
        self.modeL = Label(frame, text="SFTP", relief="ridge", borderwidth=2)
        self.modeL.grid(row=1, column=3, sticky=W)

        Label(frame, text="name:").grid(row=2, column=0, sticky=W)
        self.nameE = Entry(frame)
        self.nameE.grid(row=2, column=1, sticky=EW, columnspan=3)

        Label(frame, text="path:").grid(row=3, column=0, sticky=W)
        self.path = StringVar()
        self.pathE = Entry(frame, textvariable=self.path)
        self.pathE.grid(row=3, column=1, sticky=EW, columnspan=3)

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

    def set_profile(self, event=None):
        p = self.profileCB.get()
        if p:
            prof = self.conf[p]
            self.connectionCB.set(prof["host"])
            self.port = prof["port"]
            self.nameE.delete(0, END)
            self.nameE.insert(END, prof["user"])
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

    def download_worker(self, src, file, isFile=True):
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
                        self.connection.get(src, join(folder, file),
                                            encoding=self.enc, errors="replace")
                    else:
                        with open(join(folder, file), "wb+") as f:
                            self.connection.retrbinary("RETR %s" % src, f.write)
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
                if overwrite:
                    self.is_busy = True

                    # TODO recurse folder
                    # if self.mode == "SFTP":
                    #     self.connection.get(src, join(folder, file),
                    #                         encoding=self.enc, errors="replace")
                    # else:
                    #     with open(join(folder, file), "wb+") as f:
                    #         self.connection.retrbinary("RETR %s" % src, f.write)

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
            p += "/".join(self.pathE.get().split("/")[:-1]) or "/"
        else:
            p += self.pathE.get()
            p = "/".join(((p if p != "/" else ""), item_name))
        if self.mode == "SFTP" and self.connected:
            if S_ISDIR(self.connection.stat(p, encoding=self.enc, errors="replace").st_mode) != 0:
                self.pathE.delete(0, END)
                self.pathE.insert(END, p)
                self.connection.chdir(p, encoding=self.enc, errors="replace")
                self.fill(self.connection)
            else:
                Thread(target=self.download_worker,
                       args=["/".join((self.connection.getcwd(), item_name)),
                             item_name],
                       daemon=True).start()
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
                Thread(target=self.download_worker,
                       args=[item_name, item_name],
                       daemon=True).start()

    def fill(self, conn):
        self.tree.delete(*self.tree.get_children())
        if self.mode == "SFTP":
            if conn.getcwd() != "/":
                self.tree.insert("", END, text="..")
            try:
                conn.listdir_attr(".", encoding=self.enc, errors="replace")
                for f in sorted(conn.listdir_attr(".", encoding=self.enc, errors="replace"), key=(lambda f: (S_ISREG(f.st_mode) != 0, f.filename))):
                    img = ""
                    if S_ISDIR(f.st_mode) != 0:
                        img = self.d_img
                    elif S_ISREG(f.st_mode) != 0:
                        img = self.f_img
                    elif S_ISLNK(f.st_mode) != 0:
                        img = self.l_img
                    self.tree.insert("", END, text=f.filename,
                                     values=(filemode(f.st_mode),
                                             datetime.fromtimestamp(f.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                                             f.st_size, f.st_mode, f.st_mtime),
                                     image=img)
            except PermissionError:
                messagebox.showwarning("Permission Denied", "You don't have permission to see the content of this folder.")

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
                        dt = datetime.strptime(conn.voidcmd("MDTM %s" % p[0]).split()[-1], "%Y%m%d%H%M%S")
                    except Exception as e:
                        print(e)
                img = ""
                if d[0][0] == "d":
                    img = self.d_img
                elif d[0][0] == "-":
                    img = self.f_img
                elif d[0][0] == "l":
                    img = self.l_img
                self.tree.insert("", END, text=p[0],
                                 values=(d[0], dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "", d[4], d[0][0] == "d", dt.timestamp() if dt else ""),
                                 image=img)

        self.tree.focus_set()
        self.tree.focus(self.tree.get_children("")[0])

    def context(self, e):
        self.ctx = Menu(self, tearoff=False)
        self.ctx.add_command(label="Delete", command=self.delete)
        self.ctx.add_command(label="Rename", command=self.rename)
        self.ctx.add_command(label="Create new Folder", command=self.mkdir)
        self.ctx.add_command(label="Upload Folder", command=self.upload_folder)
        self.ctx.add_command(label="Upload Files", command=self.upload_file)
        self.ctx.tk_popup(e.x_root, e.y_root)

    def mkdir(self):
        name = simpledialog.askstring("Create Directory", "Enter a name for the new directory:")
        if self.mode == "SFTP":
            if name.strip():
                try:
                    self.connection.mkdir(name, encoding=self.enc)
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
                    st = self.connection.stat(path, encoding=self.enc).st_mode
                    if S_ISREG(st) > 0:
                        self.connection.remove(path, encoding=self.enc)
                    elif S_ISDIR(st) > 0:
                        for obj in self.connection.listdir(path, encoding=self.enc):
                            do_recursive("/".join([path, obj]))
                        try:
                            self.connection.rmdir(path, encoding=self.enc)
                        except:
                            print("rmdir failed: ", path)
                            try:  # some links are recognized as folders
                                self.connection.remove(path, encoding=self.enc)
                            except:
                                print("try rm failed too: ", path)
                    elif S_ISLNK(st) > 0:
                        print("lnk: ", path)
                        try:
                            self.connection.remove(path, encoding=self.enc)
                        except:
                            pass
                        try:
                            self.connection.rmdir(path, encoding=self.enc)
                        except:
                            pass
                except:
                    print("no stat: ", path)
                    try:
                        self.connection.remove(path, encoding=self.enc)
                    except:
                        pass
                    try:
                        self.connection.rmdir(path, encoding=self.enc)
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
                yesno = messagebox.askyesno("Delete Selected",
                                            "Are you sure you want to delete the selected objects?")
                if yesno:
                    for i in idx:
                        if S_ISDIR(int(self.tree.item(i, "values")[-2])) == 0:
                            self.connection.remove("/".join([self.pathE.get(), self.tree.item(i, "text")]))
                        else:
                            do_recursive("/".join([self.path.get(), self.tree.item(i, "text")]))
                        self.tree.delete(i)
        else:
            idx = self.tree.selection()
            if len(idx) > 0:
                yesno = messagebox.askyesno("Delete Selected",
                                            "Are you sure you want to delete the selected objects?")
                if yesno:
                    for i in idx:
                        if self.tree.item(i, "values")[-2] == "True":
                            do_recursive("/".join([self.pathE.get(), self.tree.item(i, "text")]))
                        else:
                            print("/".join([self.pathE.get(), self.tree.item(i, "text")]))
                            self.connection.delete("/".join([self.pathE.get(), self.tree.item(i, "text")]))
                        self.tree.delete(i)

    def rename(self):
        idx = self.tree.selection()
        if len(idx) > 0:
            name = simpledialog.askstring("Rename", "Enter new name for %s:"
                                          % self.tree.item(idx[0], "text"))
            if self.mode == "SFTP":
                if name.strip():
                    try:
                        self.connection.rename(self.tree.item(idx[0], "text"),
                                               name, encoding=self.enc)
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
        files = filedialog.askopenfilenames(title="Choose files to upload", parent=self)
        dest = simpledialog.askstring(title="Choose destination", prompt="Choose upload destination", parent=self, initialvalue=self.path.get())
        if files and len(files) > 0 and dest:
            if self.mode == "SFTP":
                self.is_busy = True
                for file in files:
                    tm = getmtime(file)
                    ta = getatime(file)
                    tgt = "%s/%s" % (dest.strip(), basename(file))
                    self.connection.put(file, tgt, encoding=self.enc)
                    self.connection.utime(tgt, (ta, tm), encoding=self.enc)
            else:
                self.is_busy = True
                for file in files:
                    try:
                        with open(file, "rb") as f:
                            self.connection.storbinary("STOR %s" % basename(file), f)
                        self.connection.voidcmd("MFMT %s %s" % (
                            datetime.fromtimestamp(getmtime(file)).strftime("%Y%m%d%H%M%S"),
                            file
                        ))
                    except Exception as e:
                        print(e)
        self.fill(self.connection)
        self.is_busy = False

    def upload_folder(self):
        folder = filedialog.askdirectory(title="Choose folder to upload", parent=self)
        dest = simpledialog.askstring(title="Choose upload destination", prompt="Input upload destination path", parent=self, initialvalue=self.path.get())

        def recurse(destination, target):
            if self.mode == "SFTP":
                if islink(target):
                    return
                elif isdir(target):
                    try:
                        self.connection.mkdir("%s/%s" % (destination, basename(target)), encoding=self.enc)
                        for f in listdir(target):
                            recurse("%s/%s" % (destination, basename(target)),
                                    "%s/%s" % (target, basename(f)))
                    except Exception as e:
                        print(target, e)
                elif isfile(target):
                    tm = getmtime(target)
                    ta = getatime(target)
                    self.connection.put(target, "%s/%s" % (destination, basename(target)), encoding=self.enc)
                    self.connection.utime("%s/%s" % (destination, basename(target)), (ta, tm), encoding=self.enc)
            else:
                if islink(target):
                    return
                elif isdir(target):
                    self.connection.mkd("%s/%s" % (destination, basename(target)))
                    for f in listdir(target):
                        recurse("%s/%s" % (destination, basename(target)),
                                "%s/%s" % (target, basename(f)))
                elif isfile(target):
                    try:
                        with open(target, "rb") as f:
                            self.connection.storbinary("STOR %s/%s" % (destination, basename(target)), f)
                        self.connection.voidcmd("MDTM %s %s" % (
                            datetime.fromtimestamp(getmtime(target)).strftime("%Y%m%d%H%M%S"),
                            "%s/%s" % (destination, basename(target))
                        ))
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
                            self.connection.mkdir(fo, encoding=self.enc)
                            self.connection.chdir(fo, encoding=self.enc)
                    self.path.set(self.connection.getcwd())
                except Exception as e:
                    pass
                if not isfile(folder):
                    try:
                        self.connection.mkdir(basename(folder))
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
                            self.connection.mkd("%s/%s" % (dest, basename(folder)))
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
            if not self.connected:
                try:
                    cli = SSHClient()
                    cli.set_missing_host_key_policy(AutoAddPolicy())
                    cli.connect(
                        self.connectionCB.get(),
                        self.port,
                        self.nameE.get(),
                        self.password,
                        timeout=10,
                        allow_agent=False)

                    connection = cli.open_sftp()
                except Exception as e:
                    print(e)
                    return

                try:
                    connection.chdir(self.pathE.get())
                except PermissionError:
                    self.connected = False
                    connection.close()
            else:
                try:
                    self.connection.close()
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
                    connection.cwd(self.pathE.get())
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
