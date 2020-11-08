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


from os import listdir, makedirs, utime, stat, remove
from os.path import exists, join as ojoin, basename, getmtime, getsize, isdir, normpath, isfile, islink
from posixpath import join as pjoin
from stat import S_ISDIR, S_ISLNK, S_ISREG, filemode
from datetime import datetime
from re import search, IGNORECASE

from ssh2.sftp import *
from ssh2.sftp import LIBSSH2_SFTP_ATTR_UIDGID, LIBSSH2_SFTP_ATTR_PERMISSIONS, LIBSSH2_SFTP_ATTR_ACMODTIME
from ssh2.sftp_handle import SFTPAttributes
from ssh2.exceptions import *
from ftplib import error_perm

from thread_work import *
from ftplisting import ftp_file_list

from tkinter import filedialog, messagebox


def insert(ui, datas):
    for da in datas:
        ui.tree.insert(
            "", "end", text=da[0],
            values=(da[1], da[2], da[3], da[4], da[5], da[6], da[7]),
            image=da[8])


def get_size(conn, mode, enc, path, size_all, isFile):
    """
    calculate overall size

    :param conn: Connection object for sftp/ftp tasks
    :type conn: object
    :param mode: Connection mode - sftp/ftp
    :type mode: str
    :param enc: encoding for the current remote login user
    :type enc: str
    :param path: file or folder to get size from
    :type path: str
    :param size_all: ref object for the result
    :type size_all: dict
    :param isFile: flag to indicate file or folder
    :type isFile: bool
    """
    if mode == "SFTP":
        if not isFile:
            def recrse(pth, obj, attr, rslt):
                if S_ISDIR(attr.permissions) != 0:
                    with conn.opendir(pjoin(pth, obj)) as dirh_:
                        for size_, buf_, attrs_ in dirh_.readdir():
                            o_ = buf_.decode(enc)
                            if o_ not in [".", ".."]:
                                recrse(pjoin(pth, obj), o_, attrs_, rslt)
                elif S_ISREG(attrs.permissions) != 0:
                    rslt["size"] += attrs.filesize

            with conn.opendir(path) as dirh:
                for size, buf, attrs in dirh.readdir():
                    o = buf.decode(enc)
                    if o not in [".", ".."]:
                        recrse(path, o, attrs, size_all)
        else:
            size_all["size"] += conn.stat(path).filesize

    else:  # FTP
        if not isFile:
            def recrse(pth, finf, rslt):
                if finf[0] == "d":
                    data = ftp_file_list(conn, pth)
                    for x in data.items():
                        recrse(pjoin(pth, x[0]), x[1], rslt)
                elif finf[0] == "-":
                    rslt["size"] += int(finf.split()[4])

            dat = ftp_file_list(conn, path)
            for inf in dat.items():
                recrse(pjoin(path, inf[0]), inf[1], size_all)
        else:
            size_all["size"] += conn.size(path)


class Connection:
    """ manage all remote work with a ui thread and an thread for remote work """
    def __init__(self, mode, host, port, name, password, encoding, path, ui=None):
        """
        constructor for Connection

        :param mode: Connection mode - sftp/ftp
        :type mode: str
        :param host: host name or ip address for remote server
        :type host: str
        :param port: port number for remote connection
        :type port: int
        :param name: user name for remote login
        :type name: str
        :param password: password for remote login user
        :type password: str
        :param encoding: encoding for remote login user
        :type encoding: str
        :param path: path on remote server
        :type path: str
        :param ui: root Tk object
        :type ui: Tk
        """
        self.cwd = path
        self._mode = mode
        self._enc = encoding

        self._worker = ThreadWork(mode, host, port, name, password, encoding, 20, "worker", max_size=0, ui=ui)
        self._ui_worker = ThreadWork(mode, host, port, name, password, encoding, 15, "ui_worker", max_size=2, ui=ui)

        self.stop_search = False

    def connect(self, mode, host, port, name, password, encoding, path, ui=None):
        """
        create or re-create connection (aborts current connection)

        :param mode: Connection mode - sftp/ftp
        :type mode: str
        :param host: host name or ip address for remote server
        :type host: str
        :param port: port number for remote connection
        :type port: int
        :param name: user name for remote login
        :type name: str
        :param password: password for remote login user
        :type password: str
        :param encoding: encoding for remote login user
        :type encoding: str
        :param path: path on remote server
        :type path: str
        :param ui: root Tk object
        :type ui: Tk
        """

        if self._worker:
            self._worker.quit()
        if self._ui_worker:
            self._ui_worker.quit()

        self._mode = mode
        self._enc = encoding
        self.cwd = path

        self._worker = ThreadWork(mode, host, port, name, password, encoding, 20, "worker", ui=ui)
        self._ui_worker = ThreadWork(mode, host, port, name, password, encoding, 15, "ui_worker", ui=ui)

        if ui:
            ui.progress.configure(value=0)
            self.get_listing(ui, path, ui.fill_tree_done)

    def disconnect(self, callback=None):
        """
        disconnect the worker and abort all current tasks

        :param callback: function object
        :type callback: any
        """
        if self._worker:
            self._worker.disconnect()
        if self._ui_worker:
            self._ui_worker.disconnect()

        if callback:
            callback()

    def progress_indeterminate_start(self, ui):
        ui.progress.configure(value=0, mode="indeterminate")
        ui.progress.start()

    def progress_reset(self, ui):
        ui.progress.stop()
        ui.progress.configure(value=0, mode="determinate")

    def _get_listing_worker(self, conn, ui_, path_, enc, cb, sel):
        """
        get the content of the defined path and insert it to the root view

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param path_: work directory
        :type path_: str
        :param enc: encoding for the current remote login user
        :type enc: str
        :param cb: callback function object
        :type cb: function
        :param sel: selected item
        :type sel: str
        """
        self.progress_indeterminate_start(ui_)
        result = []
        if self._mode == "SFTP":
            try:
                if not path_:
                    channel = conn.session.open_session()
                    channel.execute('pwd')
                    channel.wait_eof()
                    channel.close()
                    channel.wait_closed()
                    self.cwd = channel.read()[1].decode(enc).strip()
                else:
                    self.cwd = path_
                with conn.opendir(self.cwd) as dirh:
                    dat = []
                    for size, buf, attrs in sorted(dirh.readdir(),
                                                   key=(lambda f: (S_ISREG(f[2].permissions) != 0, f[1]))):
                        obj = buf.decode(enc)
                        if obj == "." or (self.cwd == "/" and obj == ".."):
                            continue

                        tpe = None
                        if S_ISDIR(attrs.permissions) != 0:
                            tpe = ui_.d_img
                        elif S_ISREG(attrs.permissions) != 0:
                            tpe = ui_.f_img
                        elif S_ISLNK(attrs.permissions) != 0:
                            tpe = ui_.l_img

                        dat.append([
                            obj, filemode(attrs.permissions),
                            datetime.fromtimestamp(attrs.mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            attrs.filesize, attrs.uid, attrs.gid, attrs.permissions, attrs.mtime, tpe
                        ])

                    ui_.update_main_thread_from_thread(insert, [dat, ])

                    for iid in ui_.tree.get_children():
                        if ui_.selected and ui_.selected == ui_.tree.item(iid, "text"):
                            ui_.tree.see(iid)
                            ui_.tree.selection_set(iid)
                            ui_.tree.focus(iid)

            except SocketRecvError:
                messagebox.showinfo("Lost connection", "The connection was lost.", parent=ui_)
                self.progress_reset(ui_)
                return
            except (PermissionError, SFTPProtocolError, SFTPHandleError) as e:
                messagebox.showwarning(
                    "Permission Denied",
                    "You don't have permission to see the content of this folder.",
                    parent=ui_
                )
                self.progress_reset(ui_)
                return

        else:  # FTP
            if self.cwd != "/":
                insert(ui_, [["..", "", "", "", "", "", True, "", ui_.d_img], ])
            if not path_:
                self.cwd = conn.pwd()

            data = ftp_file_list(conn, self.cwd)
            ui_data = []

            for p in sorted(data.items(), key=lambda x: (x[1][0] == "-", x[0].lower())):
                if not self._ui_worker.isConnected():
                    self.progress_reset(ui_)
                    return

                d = p[1].split()
                dt = None
                if d[7].isnumeric():
                    dt = datetime.strptime(f"{d[5]}{d[6]}{d[7]}00:00", "%b%d%Y%H:%M")
                else:
                    dt = datetime.strptime(f"{d[5]}{d[6]}{datetime.now().year}{d[7]}", "%b%d%Y%H:%M")
                # if d[0][0] != "d":
                #     try:
                #         dt = datetime.strptime(
                #             conn.voidcmd("MDTM %s" % p[0]).split()[-1],
                #             "%Y%m%d%H%M%S"
                #         )
                #     except Exception as e:
                #         print(e)

                tpe = None
                if d[0][0] == "d":
                    tpe = ui_.d_img
                elif d[0][0] == "-":
                    tpe = ui_.f_img
                elif d[0][0] == "l":
                    tpe = ui_.l_img

                ui_data.append([
                    p[0], d[0],
                    dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
                    d[4], d[2], d[3], d[0][0] == "d", dt.timestamp() if dt else "", tpe
                ])

            ui_.update_main_thread_from_thread(insert, [ui_data, ])

        self.progress_reset(ui_)
        ui_.path.set(self.cwd)

        if not sel and cb:
            cb()

    def _cwd_dnl_worker(self, conn, ui_, path_, enc, item_nfo, updatefunc, donefunc):
        """
        change into directory or start download of file - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param path_: file or directory
        :type path_: str
        :param enc: encoding for the current remote login user
        :type enc: str
        :param item_nfo: struct with information about path_
        :type item_nfo: object
        :param updatefunc: callback function for updating the ui (download progress)
        :type updatefunc: function
        :param donefunc: callback function to inform the user about the end of the download
        :type donefunc: function
        """
        last = basename(self.cwd)
        if self._mode == "SFTP":
            inf = None
            if not path_:
                channel = conn.session.open_session()
                channel.execute('pwd')
                channel.wait_eof()
                channel.close()
                channel.wait_closed()
                p = channel.read()[1].decode(enc).strip()
                if p:
                    path_ = normpath(p).replace("\\", "/")
                self.cwd = path_
            try:
                inf = conn.stat(path_)
            except SFTPProtocolError:
                messagebox.showerror("Path Error",
                                     "No such path or no permission to see this path.",
                                     parent=ui_)
                return

            if S_ISDIR(inf.permissions) != 0:
                self.cwd = normpath(path_).replace("\\", "/")
                donefunc(refresh=True, path=self.cwd, selected=last)
            else:
                if S_ISLNK(conn.lstat(path_).permissions) != 0:
                    messagebox.showerror("Not supported",
                                         "Can't download links yet.",
                                         parent=ui_)
                    return
                if item_nfo[0]:
                    destination = filedialog.askdirectory(
                        title="Choose download destination",
                        parent=ui_
                    )
                    if not destination:
                        return
                    self.download(
                        ui_,
                        pjoin(self.cwd, item_nfo[0]),
                        item_nfo[0],
                        (inf.atime, inf.mtime),
                        updatefunc,
                        donefunc,
                        True,
                        destination,
                        inf.filesize
                    )
        elif self._mode == "FTP" and conn:
            fd = False
            if not item_nfo or item_nfo[0] == ".." or item_nfo[1][0] != "-":
                try:  # Try to change into path. If we can't, then it's either a file or insufficient permissions
                    conn.cwd(path_)
                    self.cwd = normpath(path_).replace("\\", "/")
                    donefunc(refresh=True, message="", path=self.cwd)
                    fd = True
                except error_perm:
                    if item_nfo[1][0] == "l":
                        messagebox.showerror("Not supported",
                                             "Can't download links yet.",
                                             parent=ui_)
                        return
                    elif not item_nfo or item_nfo[1][0] not in ["-", ]:
                        messagebox.showerror("Path Error",
                                             "No such path or no permission to see this path.",
                                             parent=ui_)
                        return
                except Exception as e:
                    print(type(e), str(e))
                    if not item_nfo or item_nfo[1][0] not in ["-", ]:
                        messagebox.showerror("Path Error",
                                             "No such path or no permission to see this path.",
                                             parent=ui_)
                        return
            if not fd:
                ts = datetime.strptime(
                    item_nfo[2],
                    "%Y-%m-%d %H:%M:%S").timestamp()
                destination = filedialog.askdirectory(
                    title="Choose download destination",
                    parent=ui_
                )
                if not destination:
                    return
                self.download(ui_, self.cwd, item_nfo[0], (ts, ts), updatefunc, donefunc, True, destination, item_nfo[3])

        # donefunc(message=True)

    def _search_worker(self, conn, path_, recursive_, depth_, filename_, sensitive_, regex_, resultfunc, donefunc):
        """
        search for a file in the current path or in its subfolders - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param path_: file or directory
        :type path_: str
        :param recursive_: flag to search in subfolders
        :type recursive_: bool
        :param depth_: maximum depth of path
        :type depth_: int
        :param filename_: name/pattern to search for
        :type filename_: str
        :param sensitive_: flag for case sensitivity
        :type sensitive_: bool
        :param regex_: flag to use regular expressions to search with
        :type regex_: bool
        :param resultfunc: callback function to return results to UI
        :type resultfunc: function
        :param donefunc: callback to inform user about the end of search
        :type donefunc: function
        """
        if self._mode == "SFTP":
            def recurse(pth):
                current_depth = len(pth[len(path_):].split("/"))
                if self.stop_search or (not recursive_ and current_depth > 1) or 0 < depth_ < current_depth:
                    return
                try:
                    with conn.opendir(pth) as dirh:
                        for size, buf, attrs in sorted(
                                dirh.readdir(),
                                key=(lambda f: (S_ISREG(f[2].permissions) != 0, f[1]))):
                            obj = buf.decode(self._enc)
                            if obj in [".", ".."]:
                                continue
                            if S_ISDIR(attrs.permissions) != 0:
                                recurse(pjoin(pth, obj))
                            elif S_ISREG(attrs.permissions) != 0:
                                if not regex_ and ((sensitive_ and filename_ in obj) or (
                                        not sensitive_ and filename_.lower() in obj.lower())):
                                    resultfunc(pjoin(pth, obj))
                                elif regex_ and search(filename_, obj, 0 if sensitive_ else IGNORECASE):
                                    resultfunc(pjoin(pth, obj))
                            elif S_ISLNK(attrs.permissions) != 0:
                                recurse(pjoin(pth, obj))
                except SocketRecvError as e:
                    messagebox.showinfo("Lost connection", "The connection was lost.")
                except (PermissionError, SFTPProtocolError, SFTPHandleError) as e:
                    print("error", type(e), str(e))

            recurse(path_)
        else:  # FTP
            def recurse(pth):
                current_depth = len(pth[len(path_):].split("/"))
                if self.stop_search or (not recursive_ and current_depth > 1) or 0 < depth_ < current_depth:
                    return
                try:
                    data = ftp_file_list(conn, pth)
                    for p, i in data.items():
                        d = i.split()
                        if d[0][0] == "d":
                            recurse(pjoin(pth, p))
                        elif d[0][0] == "-":
                            if not regex_ and ((sensitive_ and filename_ in p) or (
                                    not sensitive_ and filename_.lower() in p.lower())):
                                resultfunc(pjoin(pth, p))
                            elif regex_ and search(filename_, p, 0 if sensitive_ else IGNORECASE):
                                resultfunc(pjoin(pth, p))
                        elif d[0][0] == "l":
                            recurse(pjoin(pth, p))
                except Exception as e:
                    print(type(e), str(e))

            recurse(path_)

        donefunc()

    def _download_worker(self, conn, ui_, src_, file_, ts_, updatefunc, donefunc, isFile_=True, destination_="",
                         size_sum_=None):
        """
        download files or folders - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param src_: original path
        :type src_: str
        :param file_: name of object (file or folder)
        :type file_: str
        :param ts_: timestamp tuple (atime, mtime)
        :type ts_: tuple
        :param updatefunc: callback function to update the UI
        :type updatefunc: function
        :param donefunc: callback function to inform the user about the end of a download
        :type donefunc: function
        :param isFile_: flag: true if it's a file else false
        :type isFile_: bool
        :param destination_: destination to download to
        :type destination_: str
        :param size_sum_: overall bytes to download
        :type size_sum_: int
        """
        if isFile_:
            if updatefunc:
                updatefunc(maximum=size_sum_ if size_sum_ else 0)
            if destination_:
                overwrite = True
                if exists(ojoin(destination_, file_)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing file?",
                        "A file with the same name already exists. Do you want to override it?",
                        parent=ui_)
                if overwrite:
                    if self._mode == "SFTP":
                        try:
                            with conn.open(src_, LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as inpt:
                                fstat = inpt.fstat()
                                with open(ojoin(destination_, file_), "wb") as f:
                                    while True:
                                        res, buf = inpt.read()
                                        if not buf:
                                            break
                                        else:
                                            f.write(buf)
                                            if updatefunc:
                                                updatefunc(step=len(buf))
                                utime(ojoin(destination_, file_), (fstat.atime, fstat.mtime))
                        except SCPProtocolError:
                            raise Exception("Insufficient Permissions")
                            # messagebox.showerror("Insufficient Permissions",
                            #                      "Could not receive file because of insufficient permissions.",
                            #                      parent=ui_)

                    else:
                        try:
                            conn.cwd(self.cwd)
                            csize = {"s": 0}

                            def handleDownload(block, fi, size_):
                                size_["s"] += len(block)
                                fi.write(block)
                                if updatefunc:
                                    updatefunc(value=size_["s"])

                            self._worker.fileDescriptor = open(ojoin(destination_, file_), "wb+", buffering=1024*1024*10)
                            conn.retrbinary("RETR %s" % pjoin(src_, file_),
                                            lambda blk: handleDownload(blk, self._worker.fileDescriptor, csize),
                                            blocksize=1024*1024*10)
                            utime(ojoin(destination_, file_), ts_)
                        except error_perm:
                            self._worker.fileDescriptor.close()
                            messagebox.showerror("Insufficient Permissions",
                                                 "Could not receive file because of insufficient permissions.",
                                                 parent=ui_)
                            remove(ojoin(destination_, file_))
        else:
            if destination_:
                overwrite = True
                if exists(ojoin(destination_, file_)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing files?",
                        "A folder with the same name already exists. Do you want to override all contained files?",
                        parent=ui_)
                else:
                    makedirs(ojoin(destination_, file_), exist_ok=True)
                if overwrite:
                    if self._mode == "SFTP":
                        def recurse(orig, path, fi):
                            if S_ISDIR(fi[1].permissions) != 0:
                                makedirs(path, exist_ok=True)
                                with conn.opendir(orig) as dirh_:
                                    for size_, buf_, attrs_ in dirh_.readdir():
                                        o_ = buf_.decode(self._enc)
                                        if o_ not in [".", ".."]:
                                            recurse(pjoin(orig, o_), pjoin(path, o_), (o_, attrs_))
                            elif S_ISREG(fi[1].permissions) != 0:
                                try:
                                    with conn.open(src_, LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as inpt:
                                        fstat = inpt.fstat()
                                        with open(ojoin(destination_, file_), "wb") as f:
                                            while True:
                                                res, buf = inpt.read()
                                                if not buf:
                                                    break
                                                else:
                                                    f.write(buf)
                                                    if updatefunc:
                                                        updatefunc(step=len(buf))
                                        utime(ojoin(destination_, file_), (fstat.atime, fstat.mtime))
                                except SCPProtocolError:
                                    raise Exception("Insufficient Permissions")
                                    # messagebox.showerror("Insufficient Permissions",
                                    #                      "Could not receive file because of insufficient permissions.",
                                    #                      parent=ui_)
                        size_all = {"size": size_sum_ if size_sum_ is not None else 0}
                        if size_sum_ is None:
                            if updatefunc:
                                updatefunc(mode="indeterminate", start=True, maximum=100)
                                get_size(conn, self._mode, self._enc, src_, size_all, isFile=False)
                                updatefunc(mode="determinate", stop=True, maximum=size_all["size"], value=0)

                        with conn.opendir(src_) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                o = buf.decode(self._enc)
                                if o not in [".", ".."]:
                                    recurse(pjoin(src_, o), pjoin(destination_, file_, o), (o, attrs))
                    else:  # FTP
                        conn.cwd(self.cwd)

                        def recurse(path, fi):
                            # print(path, fi)
                            if fi[0] == "d":
                                makedirs(ojoin(destination_, path[len(src_) + 1:]), exist_ok=True)
                                data = ftp_file_list(conn, path)
                                for x in data.items():
                                    recurse(pjoin(path, x[0]), x[1])
                            elif fi[0] == "-":
                                # print("local", pjoin(destination, file, basename(path)))
                                # print("remote", path)
                                csize = {"": 0}

                                def handleDownload(block, fi, size_):
                                    fi.write(block)
                                    size_[""] += len(block)
                                    if updatefunc:
                                        updatefunc(value=size_[""])

                                with open(ojoin(destination_, path[len(src_) + 1:]), "wb+") as fil:
                                    conn.retrbinary("RETR %s" % path,
                                                    lambda blk: handleDownload(blk, fil, csize))
                                try:
                                    dt = None
                                    if ":" in fi[-5:]:
                                        dt = datetime.strptime(
                                            datetime.now().strftime("%Y") + " ".join(fi.split()[-3:]), "%Y%b %d %H:%M")
                                    else:
                                        dt = datetime.strptime(" ".join(fi.split()[-3:]), "%b %d %Y")
                                    utime(ojoin(destination_, path[len(src_) + 1:]), (dt.timestamp(), dt.timestamp()))
                                except Exception as e:
                                    print(type(e), e, path)

                        size_all = {"size": size_sum_ if size_sum_ is not None else 0}
                        if size_sum_ is None:
                            if updatefunc:
                                updatefunc(mode="indeterminate", start=True, maximum=100)
                                get_size(conn, self._mode, self._enc, pjoin(src_, file_), size_all, isFile=False)
                                updatefunc(mode="determinate", stop=True, maximum=size_all["size"], value=0)

                        dat = ftp_file_list(conn, pjoin(src_, file_))
                        for inf in dat.items():
                            recurse(pjoin(src_, file_, inf[0]), inf[1])

        if donefunc:
            donefunc(message="Download done!")

    def _download_multi_worker(self, conn, ui_, sel, updatefunc, donefunc):
        """
        download multiple objects from selected items - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param sel: list of selected item objects (including metadata)
        :type sel: list of objects
        :param updatefunc: callback function to update the UI
        :type updatefunc: function
        :param donefunc: callback function to inform the user about the end of all downloads
        :type donefunc: function
        """
        destination = filedialog.askdirectory(
            title="Choose download destination")
        if not destination:
            return
        updatefunc(value=0, maximum=100, mode="indeterminate", start=True)
        size_all = {"size": 0}
        for item in sel:
            isFile = item["values"][0][0] == "-"
            get_size(conn, self._mode, self._enc, pjoin(self.cwd, item["text"]), size_all, isFile)
        updatefunc(mode="determinate", stop=True, maximum=size_all["size"], value=0)

        for item in sel:
            if item["values"][0][0] == "l":
                messagebox.showwarning("Not supported",
                                       "Can't download links yet. Skipping link.",
                                       parent=ui_)
                continue
            isFile = item["values"][0][0] == "-"
            if self._mode == "SFTP":
                nfo = conn.lstat(pjoin(self.cwd, item["text"]))  # Do not follow links
                self.download(ui_, pjoin(self.cwd, item["text"]), item["text"], (nfo.atime, nfo.mtime),
                              updatefunc, donefunc, isFile, destination, size_all["size"])
            else:
                ts = None
                if item["values"][-2]:
                    try:
                        ts = datetime.strptime(
                            conn.voidcmd("MDTM %s" % pjoin(self.cwd, item["text"])).split()[-1],
                            "%Y%m%d%H%M%S"
                        ).timestamp()
                    except:
                        pass
                self.download(ui_, self.cwd, item["text"], (ts, ts),
                              updatefunc, donefunc, isFile, destination, size_all["size"])

    def _upload_files_worker(self, conn, ui_, files_, destination, updatefunc, donefunc):
        """
        upload multiple local files - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param files_: files to upload
        :type files_: list of str
        :param destination: remote destination path
        :type destination: str
        :param updatefunc: callback function to update the UI
        :type updatefunc: function
        :param donefunc: callback function to inform the user about the end of all uploads
        :type donefunc: function
        """
        if files_ and len(files_) > 0 and destination:
            if self._mode == "SFTP":
                # dat = []
                for file in files_:
                    fifo = stat(file)
                    # chan = conn.session.scp_send64(
                    #     pjoin(destination.strip(), basename(file)),
                    #     fifo.st_mode & 0o777,
                    #     fifo.st_size,
                    #     fifo.st_mtime, fifo.st_atime)
                    # with open(file, 'rb') as lofi:
                    #     while True:
                    #         data = lofi.read(10 * 1024 * 1024)
                    #         if not data:
                    #             break
                    #         else:
                    #             _, sz = chan.write(data)
                    #             if updatefunc:
                    #                 updatefunc(step=sz)
                    mode = LIBSSH2_SFTP_S_IRUSR | \
                           LIBSSH2_SFTP_S_IWUSR | \
                           LIBSSH2_SFTP_S_IRGRP | \
                           LIBSSH2_SFTP_S_IROTH
                    f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
                    with open(file, 'rb') as lofi:
                        try:
                            with conn.open(pjoin(destination.strip(), basename(file)), f_flags, mode) as remfi:
                                while True:
                                    data = lofi.read(1024 * 1024)
                                    if not data:
                                        break
                                    else:
                                        _, sz = remfi.write(data)
                                        if updatefunc:
                                            updatefunc(step=sz)
                                attrs = SFTPAttributes()
                                attrs.flags = LIBSSH2_SFTP_ATTR_UIDGID | \
                                              LIBSSH2_SFTP_ATTR_ACMODTIME | \
                                              LIBSSH2_SFTP_ATTR_PERMISSIONS
                                attrs.atime = fifo.st_atime
                                attrs.mtime = fifo.st_mtime
                                attrs.permissions = fifo.st_mode
                                attrs.gid = fifo.st_gid
                                attrs.uid = fifo.st_uid
                                remfi.fsetstat(attrs)
                        except SFTPProtocolError:
                            raise Exception("Insufficient Permissions")

                    # dat.append([
                    #     basename(file), filemode(fifo.st_mode),
                    #     datetime.fromtimestamp(fifo.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    #     fifo.st_size, fifo.st_uid, fifo.st_gid, fifo.st_mode, fifo.st_mtime, ui_.f_img
                    # ])
                
                # ui_.update_main_thread_from_thread(insert, [dat, ])

            else:
                conn.cwd(self.cwd)
                # dat = []
                for file in files_:
                    fifo = stat(file)
                    try:
                        def handl(blk):
                            if updatefunc:
                                updatefunc(step=len(blk))

                        with open(file, "rb") as f:
                            conn.storbinary(
                                "STOR %s" % pjoin(destination, basename(file)), f, callback=handl
                            )
                        conn.voidcmd("MFMT %s %s" % (
                            datetime.fromtimestamp(
                                getmtime(file)
                            ).strftime("%Y%m%d%H%M%S"),
                            file
                        ))
                    except Exception as e:
                        print(type(e), str(e))

                    # dat.append([
                    #     file, filemode(fifo.st_mode),
                    #     datetime.fromtimestamp(fifo.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    #     fifo.st_size, fifo.st_uid, fifo.st_gid, fifo.st_mode, fifo.st_mtime,
                    #     ui_.f_img
                    # ])
                # ui_.update_main_thread_from_thread(insert, [dat, ])

        donefunc(message="Upload done!", refresh=True)

    def _upload_folder_worker(self, conn, ui_, folder_, destination_, updatefunc, donefunc):
        """
        upload local folder - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param folder_: local folder to upload
        :type folder_: str
        :param destination_: remote destination path
        :type destination_: str
        :param updatefunc: callback function to update the UI
        :type updatefunc: function
        :param donefunc: callback function to inform the user about the end of uploads
        :type donefunc: function
        """
        size_all = {"size": 0}

        if folder_:
            updatefunc(mode="indeterminate", value=100, start=True)

            def recrse(pth, rslt):
                for f in listdir(pth):
                    fp = ojoin(pth, f)
                    if isfile(fp) and not islink(fp):
                        rslt["size"] += getsize(fp)
                    elif isdir(fp) and not islink(fp):
                        recrse(fp, rslt)

            recrse(folder_, size_all)
            updatefunc(mode="determinate", maximum=size_all["size"], value=0, stop=True)

        def recurse(dest, target):
            if self._mode == "SFTP":
                if islink(target):
                    return
                elif isdir(target):
                    try:
                        flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                               LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                               LIBSSH2_SFTP_S_IROTH
                        conn.mkdir(pjoin(dest, basename(target)), flgs)
                        for f in listdir(target):
                            recurse(pjoin(dest, basename(target)),
                                    pjoin(target, basename(f)))
                    except Exception as e:
                        print(target, type(e), str(e))
                elif isfile(target):
                    fifo = stat(target)
                    mode = LIBSSH2_SFTP_S_IRUSR | \
                           LIBSSH2_SFTP_S_IWUSR | \
                           LIBSSH2_SFTP_S_IRGRP | \
                           LIBSSH2_SFTP_S_IROTH
                    f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
                    with open(target, 'rb') as lofi:
                        # print("target", target)
                        # print("dest", pjoin(dest.strip(), basename(target)))
                        with conn.open(
                                pjoin(dest.strip(), basename(target)),
                                f_flags, mode) as remfi:
                            while True:
                                data = lofi.read(1024*1024)
                                if not data:
                                    break
                                else:
                                    remfi.write(data)
                                    updatefunc(step=len(data))
                            attrs = SFTPAttributes()
                            attrs.flags = LIBSSH2_SFTP_ATTR_UIDGID | \
                                          LIBSSH2_SFTP_ATTR_ACMODTIME | \
                                          LIBSSH2_SFTP_ATTR_PERMISSIONS
                            attrs.atime = fifo.st_atime
                            attrs.mtime = fifo.st_mtime
                            attrs.permissions = fifo.st_mode
                            attrs.gid = fifo.st_gid
                            attrs.uid = fifo.st_uid
                            remfi.fsetstat(attrs)
            else:
                conn.cwd(self.cwd)
                if islink(target):
                    return
                elif isdir(target):
                    conn.mkd(
                        pjoin(dest, basename(target))
                    )
                    for f in listdir(target):
                        recurse(pjoin(dest, basename(target)),
                                pjoin(target, basename(f)))
                elif isfile(target):
                    try:
                        def handl(blk):
                            updatefunc(step=len(blk))

                        with open(target, "rb") as f:
                            conn.storbinary(
                                "STOR %s" % pjoin(dest, basename(target)),
                                f, callback=handl
                            )
                        conn.voidcmd(
                            "MDTM %s %s" % (
                                datetime.fromtimestamp(
                                    getmtime(target)
                                ).strftime("%Y%m%d%H%M%S"),
                                pjoin(dest, basename(target))
                            )
                        )
                    except Exception as e:
                        print(type(e), str(e))

        if folder_ and destination_:
            if self._mode == "SFTP":
                try:
                    p = self.cwd
                    tmp = ""
                    if p in destination_:
                        tmp += destination_[len(p) + 1:]  # +1 to remove slash
                    for fo in tmp.split("/"):
                        if fo:
                            # conn.mkdir(fo, encoding=rt.enc)
                            # conn.chdir(fo, encoding=rt.enc)
                            flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                                   LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                                   LIBSSH2_SFTP_S_IROTH
                            conn.mkdir(fo, flgs)
                    # rt.path.set(normpath(pjoin(p, fo)))
                except Exception as e:
                    print(type(e), str(e))
                if not isfile(folder_):
                    try:
                        # conn.mkdir(basename(folder))
                        flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                               LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                               LIBSSH2_SFTP_S_IROTH
                        conn.mkdir(pjoin(self.cwd, basename(folder_)), flgs)
                    except Exception as e:
                        pass
            else:
                conn.cwd(self.cwd)
                try:
                    p = self.cwd
                    tmp = ""
                    if p in destination_:
                        tmp += destination_[len(p) + 1:]  # +1 to remove slash
                    ctmp = p
                    for fo in tmp.split("/"):
                        try:
                            if fo:
                                conn.mkd(pjoin(ctmp, fo))
                                ctmp += "/" + fo
                        except Exception as e:
                            print(ctmp, e)
                    conn.mkd(
                        pjoin(destination_, basename(folder_))
                    )
                    # rt.path.set(conn.pwd())
                except Exception as e:
                    print("mkdir orig2 err:", e)
            for f_ in listdir(folder_):
                recurse(normpath(pjoin(destination_, basename(folder_))).replace("\\", "/"),
                        normpath(pjoin(folder_, basename(f_))).replace("\\", "/"))

            donefunc(message="Upload done!", refresh=True)

            # insert(ui_, [[folder_, "d?????????", "", "", "", "", True, "", ui_.d_img], ])

    def _mkdir_worker(self, conn, ui_, name_, cb):
        """
        create a remote folder - execute in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param name_: name of the new remote folder
        :type name_: str
        :param cb: callback function to update the UI
        :type cb: function
        """
        self.progress_indeterminate_start(ui_)

        if self._mode == "SFTP":
            try:
                flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                       LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                       LIBSSH2_SFTP_S_IROTH
                conn.mkdir(pjoin(self.cwd, name_), flgs)
            except Exception as e:
                print(e)
        else:
            try:
                conn.cwd(self.cwd)
                conn.mkd(name_)
            except Exception as e:
                print(e)

        cb(refresh=True)

        # insert(ui_, [[name_, "d?????????", "", "", "", "", True, "", ui_.d_img], ])

        self.progress_reset(ui_)

    def _rename_worker(self, conn, ui_, orig, new_, cb):
        """
        rename remote object - executed in separate thread

        :param conn: Connection object for sftp/ftp tasks
        :type conn: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param orig: original object name
        :type orig: str
        :param new_: new object name
        :type new_: str
        :param cb: callback function to update the UI
        :type cb: function
        """
        self.progress_indeterminate_start(ui_)
        if self._mode == "SFTP":
            try:
                conn.rename(
                    pjoin(self.cwd, orig),
                    pjoin(self.cwd, new_))
            except Exception as e:
                print(e)
        else:
            try:
                conn.cwd(self.cwd)
                conn.rename(orig, new_)
            except Exception as e:
                print(e)

        self.progress_reset(ui_)
        cb()

    def _delete_worker(self, connection, ui_, list__, callback_):
        """
        delete remote objects - executed in separate thread

        ::param connection: Connection object for sftp/ftp tasks
        :type connection: object
        :param ui_: root Tk object
        :type ui_: Tk
        :param list__: list of remote objects to delete
        :type list__: list of str
        :param callback_: callback function to update the UI
        :type callback_: function
        """
        self.progress_indeterminate_start(ui_)

        def do_recursive(path):
            if self._mode == "SFTP":
                try:
                    st = connection.stat(path).permissions
                    if S_ISREG(st) != 0:
                        connection.unlink(path)
                    elif S_ISDIR(st) != 0:
                        with connection.opendir(path) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                if buf.decode(self._enc) not in [".", ".."]:
                                    do_recursive(pjoin(path, buf.decode(self._enc)))
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
                    connection.cwd(self.cwd)
                    connection.delete(path)
                except Exception as e:
                    try:
                        for obj in connection.nlst(path):
                            print(obj)
                            do_recursive(obj)
                        connection.rmd(path)
                    except Exception:
                        pass

        for i in list__:
            if i[1] in ["..", "."]:
                continue
            if i[2][0] == "d":
                do_recursive(pjoin(self.cwd, i[1]))
            else:
                if self._mode == "SFTP":
                    connection.unlink(pjoin(self.cwd, i[1]))
                else:
                    connection.delete(pjoin(self.cwd, i[1]))

            self.progress_reset(ui_)
            if callback_:
                callback_(i[0])

    def quit(self):
        """disconnect, stop threads clear queues"""
        if self._worker:
            self._worker.quit()
        if self._ui_worker:
            self._ui_worker.quit()

    # wrapper functions for threading

    def get_listing(self, ui, path, callback, selected=""):
        ui.tree.delete(*ui.tree.get_children())
        if self._ui_worker:
            self._ui_worker.add_task(self._get_listing_worker, [ui, path, self._enc, callback, selected])

    def cwd_dnl(self, ui, path, item_info, update, done):
        if self._ui_worker:
            self._ui_worker.add_task(self._cwd_dnl_worker, [ui, path, self._enc, item_info, update, done])

    def search(self, path, recursive, depth, filename, sensitive, regex, insert_result, done):
        self.stop_search = False
        if self._ui_worker:
            self._ui_worker.add_task(self._search_worker,
                                     [path, recursive, depth, filename, sensitive, regex, insert_result, done])

    def download(self, ui, src, file, ts, update, done, isFile=True, destination="", size_sum=None):
        if self._worker:
            self._worker.add_task(self._download_worker,
                                  args=[ui, src, file, ts, update, done, isFile, destination, size_sum])

    def download_multi(self, ui, selection, update, done):
        if self._ui_worker:
            self._ui_worker.add_task(self._download_multi_worker, [ui, selection, update, done])

    def upload_files(self, ui, files, dest, update, done):
        if self._worker:
            self._worker.add_task(self._upload_files_worker, [ui, files, dest, update, done])

    def upload_folder(self, ui, folder, destination, update, done):
        if self._worker:
            self._worker.add_task(self._upload_folder_worker, [ui, folder, destination, update, done])

    def mkdir(self, ui, name, callback):
        if self._worker:
            self._worker.add_task(self._mkdir_worker, [ui, name, callback])

    def rename(self, ui, orig_name, new_name, callback):
        if self._worker:
            self._worker.add_task(self._rename_worker, [ui, orig_name, new_name, callback])

    def delete_object(self, ui, list_, callback):
        if self._worker:
            self._worker.add_task(self._delete_worker, [ui, list_, callback])

