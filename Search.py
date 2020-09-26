#!/usr/bin/env python
# -*- encoding=utf8 -*-

from os import listdir, makedirs, utime, stat, remove
from os.path import exists, join, basename, getmtime, getatime, getsize, isdir, normpath, \
    dirname, abspath, isfile, islink
from stat import S_ISDIR, S_ISLNK, S_ISREG, filemode
from datetime import datetime
from re import search, IGNORECASE
from ssh2.exceptions import *
from ftplib import error_perm

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import StringVar, IntVar, BooleanVar, messagebox

from thread_work import ThreadWork

from ftplisting import ftp_file_list


class SearchView(Toplevel):
    def __init__(self, root, current_path=""):
        super().__init__(root)

        self.stop = False
        self.parent = root
        self.worker = None

        self.geometry("600x400")
        self.geometry("+%d+%d" % (root.winfo_x() + 50, root.winfo_y() + 25))
        self.minsize(550, 300)

        pf = Labelframe(self, text="Path")
        pf.grid(sticky=EW, padx=5)

        self.path = StringVar(value=current_path)
        self.pathE = Entry(pf, textvariable=self.path)
        self.pathE.pack(fill=X, expand=True)

        rf = Labelframe(self, text="Recursive")
        rf.grid(sticky=EW, padx=5)

        self.recursive = BooleanVar(value=True)
        self.recursiveCB = Checkbutton(rf, text="Search recursive?", variable=self.recursive, command=self.setRecursive)
        self.recursiveCB.grid(row=0, sticky=EW)

        self.depthFrame = Frame(rf)
        Label(self.depthFrame, text="Max depth:").grid(row=0, column=0)
        self.depth = StringVar(value='1')
        self.depthS = Spinbox(self.depthFrame, from_=0, to=10, textvariable=self.depth)
        self.depthS.grid(row=0, column=1)
        self.depthFrame.grid(row=1, sticky=EW)

        sof = Labelframe(self, text="Search Options")
        sof.grid(sticky=EW, padx=5)

        Label(sof, text="File Name:").pack(fill=X, expand=True)
        self.filename = StringVar()
        self.filenameE = Entry(sof, textvariable=self.filename)
        self.filenameE.pack(fill=X, expand=True)

        self.sensitive = BooleanVar(value=False)
        self.sensitiveCB = Checkbutton(sof, text="Case sensitive?", variable=self.sensitive)
        self.sensitiveCB.pack(fill=X, expand=True)

        self.regex = BooleanVar(value=False)
        self.regexCB = Checkbutton(sof, text="Use Regular Expression?", variable=self.regex)
        self.regexCB.pack(fill=X, expand=True)

        btnf = Frame(self)
        btnf.grid(sticky=EW, padx=5)
        btnf.grid_columnconfigure(0, weight=1)
        btnf.grid_columnconfigure(1, weight=1)
        btnf.grid_rowconfigure(0, pad=15)

        self.searchBtn = Button(btnf, text="Search", command=self.search)
        self.searchBtn.grid(row=0, column=0)
        self.stopBtn = Button(btnf, text="Stop", command=self.do_stop)
        self.stopBtn.grid(row=0, column=1)

        scrollbar = Scrollbar(self, takefocus=0)
        self.box = Listbox(self, yscrollcommand=scrollbar.set, selectmode="single", background="white smoke")
        self.box.grid(row=0, sticky=NSEW, column=1, rowspan=10)
        # self.box.grid_columnconfigure(0, weight=1)
        # self.box.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(9, weight=2)
        # self.box.grid_rowconfigure(0, weight=1)

        scrollbar.grid(row=0, column=2, sticky=NS, rowspan=10)
        scrollbar.config(command=self.box.yview)

        Sizegrip(self).grid(column=0, columnspan=3, sticky=E)

        self.worker = ThreadWork(
            self.parent.mode,
            self.parent.connectionCB.get(),
            self.parent.port,
            self.parent.nameE.get(),
            self.parent.password,
            self.parent.enc
        )

    def setRecursive(self):
        if self.recursive.get():
            self.depthFrame.grid()
        else:
            self.depthFrame.grid_remove()

    def search(self):
        self.box.delete(0, END)

        def _worker(conn, path, recurs, depth, fname, sensitive, regex):
            if not path or not fname:
                if not path:
                    messagebox.showwarning("No search path!", "Please specify a path to search in.", parent=self)
                else:
                    messagebox.showwarning("No search pattern!", "Please specify a pattern to search.", parent=self)
            else:
                if self.parent.mode == "SFTP":
                    def recurse(pth):
                        current_depth = len(pth[len(path):].split("/"))
                        if self.stop or (not recurs and current_depth > 1) or 0 < depth < current_depth:
                            return
                        try:
                            with conn.opendir(pth) as dirh:
                                for size, buf, attrs in sorted(
                                        dirh.readdir(),
                                        key=(lambda f: (S_ISREG(f[2].permissions) != 0, f[1]))):
                                    obj = buf.decode(self.parent.enc)
                                    if obj in [".", ".."]:
                                        continue
                                    if S_ISDIR(attrs.permissions) != 0:
                                        recurse(join(pth, obj))
                                    elif S_ISREG(attrs.permissions) != 0:
                                        if not regex and ((sensitive and fname in obj) or (
                                                not sensitive and fname.lower() in obj.lower())):
                                            self.box.insert(END, join(pth, obj))
                                        elif regex and search(fname, obj, 0 if sensitive else IGNORECASE):
                                            self.box.insert(END, join(pth, obj))
                                    elif S_ISLNK(attrs.permissions) != 0:
                                        recurse(join(pth, obj))
                        except SocketRecvError:
                            messagebox.showinfo("Lost connection", "The connection was lost.", parent=self)
                        except (PermissionError, SFTPProtocolError, SFTPHandleError) as e:
                            print("error", e)
                        except Exception as e:
                            print("exception", e)
                    recurse(path)
                else:  # FTP
                    def recurse(pth):
                        current_depth = len(pth[len(path):].split("/"))
                        if self.stop or (not recurs and current_depth > 1) or 0 < depth < current_depth:
                            return
                        try:
                            data = ftp_file_list(conn, pth)
                            for p, i in data.items():
                                d = i.split()
                                if d[0][0] == "d":
                                    recurse(join(pth, p))
                                elif d[0][0] == "-":
                                    if not regex and ((sensitive and fname in p) or (not sensitive and fname.lower() in p.lower())):
                                        self.box.insert(END, join(pth, p))
                                    elif regex and search(fname, p, 0 if sensitive else IGNORECASE):
                                        self.box.insert(END, join(pth, p))
                                elif d[0][0] == "l":
                                    recurse(join(pth, p))
                        except:
                            pass
                    recurse(path)

            if self.worker:
                self.worker.q.task_done()
                if path and self.worker.q.empty():
                    messagebox.showinfo("DONE", "Search completed!\nFound %d files." % len(self.box.get(0, END)), parent=self)

        self.worker._quitting = False
        self.stop = False
        self.worker.add_task(_worker, args=[
            self.path.get(),
            self.recursive.get(),
            int(self.depth.get()),
            self.filename.get(),
            self.sensitive.get(),
            self.regex.get()
        ])

    def do_stop(self):
        self.stop = True
        self.worker.stop()

    def destroy(self, event=None):
        self.parent.search_open = False
        self.parent.search_window = None
        super().destroy()


if __name__ == "__main__":
    rt = Tk()
    sv = SearchView(rt, "test")
    rt.withdraw()
    rt.wait_window(sv)
