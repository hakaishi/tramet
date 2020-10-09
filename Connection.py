#!/usr/bin/env python
# -*- encoding=utf8 -*-

from os import listdir, makedirs, utime, stat, remove
from os.path import exists, join, basename, getmtime, getatime, getsize, isdir, normpath, \
    dirname, abspath, isfile, islink
from stat import S_ISDIR, S_ISLNK, S_ISREG, filemode
from datetime import datetime
from re import search, IGNORECASE

from ssh2.sftp import *
from ssh2.sftp_handle import SFTPAttributes
from ssh2.exceptions import *
from ftplib import FTP, error_perm

from thread_work import *
from ftplisting import ftp_file_list

from tkinter import filedialog, messagebox


class Connection:
    def __init__(self, mode, host, port, name, password, encoding, path, ui=None):
        self.cwd = path
        self._mode = mode
        self._enc = encoding

        self._worker = ThreadWork(mode, host, port, name, password, encoding, 20, "worker", max_size=100, ui=ui)
        self._ui_worker = ThreadWork(mode, host, port, name, password, encoding, 15, "ui_worker", max_size=2, ui=ui)

        self.stop_search = False

    def connect(self, mode, host, port, name, password, encoding, path, ui=None):
        if self._worker:
            self._worker.quit()
        self._worker = ThreadWork(mode, host, port, name, password, encoding, 20, "worker", ui=ui)
        if self._ui_worker:
            self._ui_worker.quit()
        self._ui_worker = ThreadWork(mode, host, port, name, password, encoding, 15, "ui_worker", ui=ui)
        self._mode = mode
        self._enc = encoding

        if ui:
            ui.progress.configure(value=0)
            self.get_listing(ui, path, ui.fill_tree)

    def disconnect(self, callback=None):
        if self._worker:
            self._worker.disconnect()
        if self._ui_worker:
            self._ui_worker.disconnect()

        if callback:
            callback()

    def _get_listing_worker(self, conn, ui_, path_, enc, cb):
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
                with conn.opendir(self.cwd) as dirh:
                    for size, buf, attrs in sorted(
                            dirh.readdir(),
                            key=(lambda f: (S_ISREG(f[2].permissions) != 0, f[1]))):
                        if buf.decode(enc) == "." or (self.cwd == "/" and buf.decode(enc) == ".."):
                            continue

                        tpe = None
                        if S_ISDIR(attrs.permissions) != 0:
                            tpe = ui_.d_img
                        elif S_ISREG(attrs.permissions) != 0:
                            tpe = ui_.f_img
                        elif S_ISLNK(attrs.permissions) != 0:
                            tpe = ui_.l_img

                        ui_.tree.insert(
                            "", "end", text=buf.decode(enc),
                            values=(
                                filemode(attrs.permissions),
                                datetime.fromtimestamp(attrs.mtime).strftime("%Y-%m-%d %H:%M:%S"),
                                attrs.filesize, attrs.uid, attrs.gid, attrs.permissions, attrs.mtime
                            ),
                            image=tpe
                        )

            except SocketRecvError:
                messagebox.showinfo("Lost connection", "The connection was lost.", parent=ui_)
                return
            except (PermissionError, SFTPProtocolError, SFTPHandleError) as e:
                messagebox.showwarning(
                    "Permission Denied",
                    "You don't have permission to see the content of this folder.",
                    parent=ui_
                )
                return

        else:  # FTP
            if self.cwd != "/":
                ui_.tree.insert("", "end", text="..", values=("", "", "", "", "", True, ""), image=ui_.d_img)
            if not path_:
                self.cwd = conn.pwd()

            data = ftp_file_list(conn, self.cwd)

            for p in sorted(data.items(), key=lambda x: (x[1][0] == "-", x[0].lower())):
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

                ui_.tree.insert("", "end", text=p[0], values=(
                    d[0],
                    dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
                    d[4],
                    d[2],
                    d[3],
                    d[0][0] == "d",
                    dt.timestamp() if dt else ""
                ), image=tpe)

        ui_.path.set(self.cwd)
        if cb:
            cb()

    def _cwd_dnl_worker(self, conn, ui_, path_, enc, item_nfo, updatefunc, donefunc):
        if self._mode == "SFTP":
            inf = None
            if not path_:
                channel = conn.session.open_session()
                channel.execute('pwd')
                channel.wait_eof()
                channel.close()
                channel.wait_closed()
                p = channel.read()[1].decode(enc).strip()
                self.cwd = normpath(path_)
            try:
                inf = conn.stat(path_)
            except SFTPProtocolError:
                messagebox.showerror("Path Error",
                                     "No such path or no permission to see this path.",
                                     parent=ui_)
                return

            if S_ISDIR(inf.permissions) != 0:
                self.cwd = normpath(path_)
                donefunc(refresh=True, path=self.cwd)
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
                    updatefunc(maximum=inf.filesize)
                    self.download(
                        ui_,
                        "/".join((self.cwd, item_nfo[0])),
                        item_nfo[0],
                        (inf.atime, inf.mtime),
                        updatefunc,
                        donefunc,
                        True,
                        destination
                    )
        elif self._mode == "FTP" and conn:
            fd = False
            if not item_nfo or item_nfo[0] == ".." or item_nfo[1][0] != "-":
                try:  # Try to change into path. If we can't, then it's either a file or insufficient permissions
                    conn.cwd(path_)
                    self.cwd = normpath(path_)
                    donefunc(refresh=True, message=False, path=self.cwd)
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
                updatefunc(maximum=item_nfo[3])
                self.download(ui_, self.cwd, item_nfo[0], (ts, ts), updatefunc, donefunc, True, destination)

        # donefunc(message=True)

    def _search_worker(self, conn, path_, recursive_, depth_, filename_, sensitive_, regex_, resultfunc, donefunc):
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
                                recurse(join(pth, obj))
                            elif S_ISREG(attrs.permissions) != 0:
                                if not regex_ and ((sensitive_ and filename_ in obj) or (
                                        not sensitive_ and filename_.lower() in obj.lower())):
                                    resultfunc(join(pth, obj))
                                elif regex_ and search(filename_, obj, 0 if sensitive_ else IGNORECASE):
                                    resultfunc(join(pth, obj))
                            elif S_ISLNK(attrs.permissions) != 0:
                                recurse(join(pth, obj))
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
                            recurse(join(pth, p))
                        elif d[0][0] == "-":
                            if not regex_ and ((sensitive_ and filename_ in p) or (
                                    not sensitive_ and filename_.lower() in p.lower())):
                                resultfunc(join(pth, p))
                            elif regex_ and search(filename_, p, 0 if sensitive_ else IGNORECASE):
                                resultfunc(join(pth, p))
                        elif d[0][0] == "l":
                            recurse(join(pth, p))
                except Exception as e:
                    print(type(e), str(e))

            recurse(path_)

        donefunc()

    def _download_worker(self, conn, ui_, src_, file_, ts_, updatefunc, donefunc, isFile_=True, destination_="",
                         size_sum_=None):
        if isFile_:
            if destination_:
                overwrite = True
                if exists(join(destination_, file_)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing file?",
                        "A file with the same name already exists. Do you want to override it?",
                        parent=ui_)
                if overwrite:
                    if self._mode == "SFTP":
                        try:
                            res = conn.session.scp_recv2(src_)
                            if res:
                                with open(join(destination_, file_), "wb+") as f:
                                    size = 0
                                    while True:
                                        siz, tbuff = res[0].read(1024 * 10)
                                        if siz < 0:
                                            print("error code:", siz)
                                            res[0].close()
                                            break
                                        size += siz
                                        if size > res[1].st_size:
                                            sz = res[1].st_size - size
                                            f.write(tbuff[:sz])
                                            if updatefunc:
                                                updatefunc(step=len(tbuff[:sz]))
                                        else:
                                            f.write(tbuff)
                                            if updatefunc:
                                                updatefunc(step=siz)
                                        if size >= res[1].st_size:
                                            res[0].close()
                                            break
                                utime(join(destination_, file_), (res[1].st_atime, res[1].st_mtime))
                        except SCPProtocolError:
                            messagebox.showerror("Insufficient Permissions",
                                                 "Could not receive file because of insufficient permissions.",
                                                 parent=self)

                    else:
                        try:
                            conn.cwd(self.cwd)

                            def handleDownload(block, fi):
                                fi.write(block)
                                if updatefunc:
                                    updatefunc(step=len(block))

                            with open(join(destination_, file_), "wb+") as f:
                                conn.retrbinary("RETR %s" % join(src_, file_), lambda blk: handleDownload(blk, f))
                            utime(join(destination_, file_), ts_)
                        except error_perm:
                            messagebox.showerror("Insufficient Permissions",
                                                 "Could not receive file because of insufficient permissions.",
                                                 parent=self)
                            remove(join(destination_, file_))
        else:
            if destination_:
                overwrite = True
                if exists(join(destination_, file_)):
                    overwrite = messagebox.askokcancel(
                        "Overwrite existing files?",
                        "A folder with the same name already exists. Do you want to override all contained files?",
                        parent=self)
                else:
                    makedirs(join(destination_, file_), exist_ok=True)
                if overwrite:
                    if self._mode == "SFTP":
                        def recurse(orig, path, fi):
                            if S_ISDIR(fi[1].permissions) != 0:
                                makedirs(path, exist_ok=True)
                                with conn.opendir(orig) as dirh_:
                                    for size_, buf_, attrs_ in dirh_.readdir():
                                        o_ = buf_.decode(self._enc)
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
                                                sze = res_[1].st_size - size_
                                                fil.write(tbuf[:sze])
                                                res_[0].close()
                                                if updatefunc:
                                                    updatefunc(step=len(tbuff[:sze]))
                                                break
                                            else:
                                                fil.write(tbuf)
                                                if updatefunc:
                                                    updatefunc(step=si)
                                            if size_ >= res_[1].st_size:
                                                res_[0].close()
                                                break
                                    utime(path,
                                          (res_[1].st_atime, res_[1].st_mtime))

                        # for obj in conn.listdir_attr(
                        #         src, encoding=self.enc
                        # ):
                        #     recurse(src, obj)
                        size_all = {"size": size_sum_ if size_sum_ is not None else 0}
                        if size_sum_ is None:
                            if updatefunc:
                                updatefunc(mode="indeterminate", start=True, maximum=100)
                                self._get_size(conn, self._mode, self._enc, src_, size_all, isFile=False)
                                updatefunc(mode="determinate", stop=True, maximum=size_all["size"], value=0)

                        with conn.opendir(src_) as dirh:
                            for size, buf, attrs in dirh.readdir():
                                o = buf.decode(self._enc)
                                if o not in [".", ".."]:
                                    recurse(join(src_, o), join(destination_, file_, o), (o, attrs))
                        print("done")
                    else:  # FTP
                        conn.cwd(self.cwd)

                        def recurse(path, fi):
                            # print(path, fi)
                            if fi[0] == "d":
                                makedirs(join(destination_, path[len(src_) + 1:]), exist_ok=True)
                                data = ftp_file_list(conn, path)
                                for x in data.items():
                                    recurse(join(path, x[0]), x[1])
                            elif fi[0] == "-":
                                # print("local", join(destination, file, basename(path)))
                                # print("remote", path)

                                def handleDownload(block, fi):
                                    fi.write(block)
                                    if updatefunc:
                                        updatefunc(step=len(block))

                                with open(join(destination_, path[len(src_) + 1:]), "wb+") as fil:
                                    conn.retrbinary("RETR %s" % path,
                                                    lambda blk: handleDownload(blk, fil))
                                try:
                                    dt = None
                                    if ":" in fi[-5:]:
                                        dt = datetime.strptime(
                                            datetime.now().strftime("%Y") + " ".join(fi.split()[-3:]), "%Y%b %d %H:%M")
                                    else:
                                        dt = datetime.strptime(" ".join(fi.split()[-3:]), "%b %d %Y")
                                    utime(join(destination_, path[len(src_) + 1:]), (dt.timestamp(), dt.timestamp()))
                                except Exception as e:
                                    print(type(e), e, path)

                        size_all = {"size": size_sum_ if size_sum_ is not None else 0}
                        if size_sum_ is None:
                            if updatefunc:
                                updatefunc(mode="indeterminate", start=True, maximum=100)
                                self._get_size(conn, self._mode, self._enc, join(src_, file_), size_all, isFile=False)
                                updatefunc(mode="determinate", stop=True, maximum=size_all["size"], value=0)

                        dat = ftp_file_list(conn, join(src_, file_))
                        for inf in dat.items():
                            recurse(join(src_, file_, inf[0]), inf[1])

        if donefunc:
            donefunc(message=True)

    @staticmethod
    def _get_size(conn, mode, enc, path, size_all, isFile):
        if mode == "SFTP":
            if not isFile:
                def recrse(pth, obj, attr, rslt):
                    if S_ISDIR(attr.permissions) != 0:
                        with conn.opendir(join(pth, obj)) as dirh_:
                            for size_, buf_, attrs_ in dirh_.readdir():
                                o_ = buf_.decode(enc)
                                if o_ not in [".", ".."]:
                                    recrse(join(pth, obj), o_, attrs_, rslt)
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
                            recrse(join(pth, x[0]), x[1], rslt)
                    elif finf[0] == "-":
                        rslt["size"] += int(finf.split()[4])

                dat = ftp_file_list(conn, path)
                for inf in dat.items():
                    recrse(join(path, inf[0]), inf[1], size_all)
            else:
                size_all["size"] += conn.size(path)

    def _download_multi_worker(self, conn, ui_, sel, updatefunc, donefunc):
        destination = filedialog.askdirectory(
            title="Choose download destination")
        if not destination:
            return
        updatefunc(value=0, maximum=100, mode="indeterminate", start=True)
        size_all = {"size": 0}
        for item in sel:
            isFile = item["values"][0][0] == "-"
            self._get_size(conn, self._mode, self._enc, "%s/%s" % (self.cwd, item["text"]), size_all, isFile)
        updatefunc(mode="determinate", stop=True, maximum=size_all["size"], value=0)

        for item in sel:
            if item["values"][0][0] == "l":
                messagebox.showwarning("Not supported",
                                       "Can't download links yet. Skipping link.",
                                       parent=ui_)
                continue
            isFile = item["values"][0][0] == "-"
            if self._mode == "SFTP":
                nfo = conn.lstat("%s/%s" % (self.cwd, item["text"]))  # Do not follow links
                self.download(ui_, "%s/%s" % (self.cwd, item["text"]), item["text"], (nfo.atime, nfo.mtime),
                              updatefunc, donefunc, isFile, destination, size_all["size"])
            else:
                ts = None
                if item["values"][-2]:
                    try:
                        ts = datetime.strptime(
                            conn.voidcmd("MDTM %s/%s" % (self.cwd, item["text"])).split()[-1],
                            "%Y%m%d%H%M%S"
                        ).timestamp()
                    except:
                        pass
                self.download(ui_, self.cwd, item["text"], (ts, ts),
                              None, donefunc, isFile, destination, size_all["size"])

    def _upload_files_worker(self, conn, ui_, files_, destination, updatefunc, donefunc):
        if files_ and len(files_) > 0 and destination:
            if self._mode == "SFTP":
                for file in files_:
                    fifo = stat(file)
                    # chan = conn.session.scp_send64(
                    #     "%s/%s" % (destination.strip(), basename(file)),
                    #     fifo.st_mode & 0o777,
                    #     fifo.st_size,
                    #     fifo.st_mtime, fifo.st_atime)
                    mode = LIBSSH2_SFTP_S_IRUSR | \
                           LIBSSH2_SFTP_S_IWUSR | \
                           LIBSSH2_SFTP_S_IRGRP | \
                           LIBSSH2_SFTP_S_IROTH
                    f_flags = LIBSSH2_FXF_CREAT | LIBSSH2_FXF_WRITE
                    with open(file, 'rb') as lofi:
                        with conn.open("%s/%s" % (destination.strip(), basename(file)), f_flags, mode) as remfi:
                            while True:
                                data = lofi.read(10 * 1024 * 1024)
                                if not data:
                                    break
                                else:
                                    _, sz = remfi.write(data)
                                    if updatefunc:
                                        updatefunc(step=sz)
                            attr = SFTPAttributes(fifo)
                            # attr.filesize = fifo.st_size
                            # print(file, datetime.fromtimestamp(fifo.st_mtime))
                            # attr.atime = fifo.st_atime
                            # attr.mtime = fifo.st_mtime
                            # attr.permissions = fifo.st_mode
                            # attr.gid = fifo.st_gid
                            # attr.uid = fifo.st_uid
                            remfi.fsetstat(attr)
                    t = conn.stat("%s/%s" % (destination.strip(), basename(file)))
                    print(datetime.fromtimestamp(t.atime), datetime.fromtimestamp(t.mtime))

                    ui_.tree.insert(
                        "", "end", text=file,
                        values=(
                            filemode(fifo.st_mode),
                            datetime.fromtimestamp(fifo.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            fifo.st_size, fifo.st_uid, fifo.st_gid, fifo.st_mode, fifo.st_mtime
                        ),
                        image=ui_.f_img
                    )

            else:
                conn.cwd(self.cwd)
                for file in files_:
                    fifo = stat(file)
                    try:
                        def handl(blk):
                            if updatefunc:
                                updatefunc(step=len(blk))

                        with open(file, "rb") as f:
                            conn.storbinary(
                                "STOR %s" % join(destination, basename(file)), f, callback=handl
                            )
                        conn.voidcmd("MFMT %s %s" % (
                            datetime.fromtimestamp(
                                getmtime(file)
                            ).strftime("%Y%m%d%H%M%S"),
                            file
                        ))
                    except Exception as e:
                        print(type(e), str(e))

                    ui_.tree.insert(
                        "", "end", text=file,
                        values=(
                            filemode(fifo.st_mode),
                            datetime.fromtimestamp(fifo.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            fifo.st_size, fifo.st_uid, fifo.st_gid, fifo.st_mode, fifo.st_mtime
                        ),
                        image=ui_.f_img
                    )

        donefunc(message=True)

    def _upload_folder_worker(self, conn, ui_, folder_, destination_, updatefunc, donefunc):
        size_all = {"size": 0}

        if folder_:
            updatefunc(mode="indeterminate", value=100, start=True)

            def recrse(pth, rslt):
                for f in listdir(pth):
                    fp = join(pth, f)
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
                        conn.mkdir("%s/%s" % (dest, basename(target)), flgs)
                        for f in listdir(target):
                            recurse("%s/%s" % (dest, basename(target)),
                                    "%s/%s" % (target, basename(f)))
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
                        # print("dest", "%s/%s" % (dest.strip(), basename(target)))
                        with conn.open(
                                "%s/%s" % (dest.strip(), basename(target)),
                                f_flags, mode) as remfi:
                            for data in lofi:
                                remfi.write(data)
                                updatefunc(step=len(data))
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
                    #     "%s/%s" % (dest.strip(), basename(target)))
                    # print(datetime.fromtimestamp(t.atime),
                    #       datetime.fromtimestamp(t.mtime))
            else:
                conn.cwd(self.cwd)
                if islink(target):
                    return
                elif isdir(target):
                    conn.mkd(
                        "%s/%s" % (dest, basename(target))
                    )
                    for f in listdir(target):
                        recurse("%s/%s" % (dest, basename(target)),
                                "%s/%s" % (target, basename(f)))
                elif isfile(target):
                    try:
                        def handl(blk):
                            updatefunc(step=len(blk))

                        with open(target, "rb") as f:
                            conn.storbinary(
                                "STOR %s/%s" % (dest, basename(target)),
                                f, callback=handl
                            )
                        conn.voidcmd(
                            "MDTM %s %s" % (
                                datetime.fromtimestamp(
                                    getmtime(target)
                                ).strftime("%Y%m%d%H%M%S"),
                                "%s/%s" % (dest, basename(target))
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
                    # rt.path.set(normpath("%s/%s" % (p, fo)))
                except Exception as e:
                    print(type(e), str(e))
                if not isfile(folder_):
                    try:
                        # conn.mkdir(basename(folder))
                        flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                               LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                               LIBSSH2_SFTP_S_IROTH
                        conn.mkdir("%s/%s" % (self.cwd, basename(folder_)), flgs)
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
                                conn.mkd("%s/%s" % (ctmp, fo))
                                ctmp += "/" + fo
                        except Exception as e:
                            print(ctmp, e)
                    conn.mkd(
                        "%s/%s" % (destination_, basename(folder_))
                    )
                    # rt.path.set(conn.pwd())
                except Exception as e:
                    print("mkdir orig2 err:", e)
            for f_ in listdir(folder_):
                recurse(normpath("%s/%s" % (destination_, basename(folder_))),
                        normpath("%s/%s" % (folder_, basename(f_))))

            donefunc(message=True)

            ui_.tree.insert(
                "", "end", text=folder_, values=("", "", "", "", "", "", ""),
                image=ui_.d_img
            )

    def _mkdir_worker(self, conn, ui_, name_, cb):
        if self._mode == "SFTP":
            try:
                flgs = LIBSSH2_FXF_CREAT | LIBSSH2_SFTP_S_IRWXU | \
                       LIBSSH2_SFTP_S_IRWXG | LIBSSH2_SFTP_S_IXOTH | \
                       LIBSSH2_SFTP_S_IROTH
                conn.mkdir(join(self.cwd, name_), flgs)
            except Exception as e:
                print(e)
        else:
            try:
                conn.cwd(self.cwd)
                conn.mkd(name_)
            except Exception as e:
                print(e)

        cb(refresh=False)

        ui_.tree.insert(
            "", "end", text=name_, values=("", "", "", "", "", "", ""),
            image=ui_.d_img
        )

    def _rename_worker(self, conn, ui_, orig, new_, cb):
        if self._mode == "SFTP":
            try:
                conn.rename(
                    join(self.cwd, orig),
                    join(self.cwd, new_))
            except Exception as e:
                print(e)
        else:
            try:
                conn.cwd(self.cwd)
                conn.rename(orig, new_)
            except Exception as e:
                print(e)

        cb()

    def _delete_worker(self, connection, list__, callback_):
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
                                    do_recursive(join(path, buf.decode(self._enc)))
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
                do_recursive("/".join([self.cwd, i[1]]))
            else:
                if self._mode == "SFTP":
                    connection.unlink("/".join([self.cwd, i[1]]))
                else:
                    connection.delete("/".join([self.cwd, i[1]]))

            if callback_:
                callback_(i[0])

    def quit(self):
        if self._worker:
            self._worker.quit()
        if self._ui_worker:
            self._ui_worker.quit()

    # wrapper functions for threading

    def get_listing(self, ui, path, callback):
        ui.tree.delete(*ui.tree.get_children())
        if self._ui_worker:
            self._ui_worker.add_task(self._get_listing_worker, [ui, path, self._enc, callback])

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
            self._worker.add_task(self._delete_worker, [list_, callback])

