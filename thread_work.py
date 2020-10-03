#!/usr/bin/env python
# -*- encoding=utf8 -*-

from threading import Thread, Timer
from queue import Queue
from time import sleep

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ssh2.exceptions import *
from ftplib import FTP

from tkinter import messagebox


class ThreadWork:
    def __init__(self, mode, host, port, name, password, enc):
        self._quitting = False
        self._mode = mode
        self._host = host
        self._port = port
        self._name = name
        self._passwd = password
        self._enc = enc
        self.q = Queue()
        self._thread = Thread(target=self._do_work, daemon=False)
        self._thread.start()
        self._connection = None
        self._timeout = None

    def check_idle(self, not_timeout=False):
        if self._timeout is None and not self.q.empty():
            self._timeout = Timer(10, self.check_idle)
            self._timeout.start()
        elif not_timeout or not self.q.empty():
            if self._timeout:
                self._timeout.cancel()
                self._timeout = None
            self._timeout = Timer(10, self.check_idle)
            self._timeout.start()
        else:
            self.disconnect()
            self._connection = None
            self._timeout.cancel()
            self._timeout = None

    def add_task(self, func, args=None):
        if func and self._connection is None:
            self.connect()
        if not func:
            self.q.put((None, None))
        elif self._connection:
            self.q.put((func, args))

    def _do_work(self):
        while not self._quitting:
            func, data = self.q.get(block=True)  # wait until something is available
            if func is None:
                if self._timeout:
                    self._timeout.cancel()
                    del self._timeout
                self.q.task_done()
                return

            if data:
                try:
                    func(self._connection, *data)
                except SocketDisconnectError:
                    messagebox.showerror("Connection Error", "Lost Connection.")
                    self.connect()
                # except Exception as e:
                #     print("Unknown exception:", e)
                #     self._connection = None
            else:
                try:
                    func(self._connection)
                except Exception as e:
                    print(e)

            self.check_idle(True)

    def disconnect(self):
        if self._connection:
            if self._mode == "SFTP":
                self._connection.session.disconnect()
            else:
                self._connection.quit()
            self._connection = None

    def connect(self):
        if self._mode == "SFTP":
            try:
                sock = socket(AF_INET, SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((self._host, self._port))
                cli = Session()
                cli.set_timeout(10000)
                cli.handshake(sock)

                cli.userauth_password(self._name, self._passwd)
                cli.set_timeout(0)
                self._connection = cli.sftp_init()

            except Timeout:
                messagebox.showerror("Connection Error", "Connection timeout on login.")
                return
            except (SocketDisconnectError, SocketRecvError):
                messagebox.showerror("Connection Error", "Could not establish a connection.")

            # except Exception as e:
            #     messagebox.showerror("Connection Error", str(e))
            #     return

        else:  # FTP
            try:
                ftp = FTP()
                ftp.encoding = self._enc
                ftp.connect(self._host, self._port, 10)
                ftp.login(self._name, self._passwd)

                self._connection = ftp
            except Exception as e:
                messagebox.showerror("Connection Error", str(e))
                return

    def stop(self):
        self.q.queue.clear()
        if self._connection:
            if self._mode == "SFTP":
                self._connection.session.disconnect()
            else:
                self._connection.quit()

    def quit(self):
        self._quitting = True
        self.q.queue.clear()
        if self._connection:
            if self._mode == "SFTP":
                self._connection.session.disconnect()
            else:
                self._connection.quit()
        self._connection = None
        self.add_task(None)  # stop loop


def singleShot(func, args=None):
    if args is None:
        args = []
    t = Thread(target=func, args=args, daemon=False)
    t.start()


__all__ = ['ThreadWork', 'singleShot']
