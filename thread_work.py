#!/usr/bin/env python
# -*- encoding=utf8 -*-

from threading import Thread, Timer
from queue import Queue, Full
from time import sleep

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ssh2.exceptions import *
from ftplib import FTP

from tkinter import messagebox


class ThreadWork:
    def __init__(self, mode, host, port, name, password, enc, timeout=10, descr="ThreadWork", max_size=10, ui=None):
        self.name = descr
        self._quitting = False
        self._mode = mode
        self._host = host
        self._port = port
        self._name = name
        self._passwd = password
        self._enc = enc
        self.q = Queue(max_size)
        self._thread = Thread(target=self._do_work, daemon=False)
        self._thread.start()
        self._connection = None
        self._timeout = None
        self._timeout_seconds = timeout
        self._running = False
        self._abort = False

        self.parent_ui = ui

    def check_idle(self, not_timeout=False):
        if self._timeout is None and self._connection is not None:
            self._timeout = Timer(10, self.check_idle)
            self._timeout.start()
            return
        if (not_timeout or self._running) and self._connection is not None:
            self._timeout.cancel()
            del self._timeout
            self._timeout = Timer(10, self.check_idle)
            self._timeout.start()
            return
        if self._connection is not None or (not self._running and not not_timeout):
            self.disconnect()
            self._connection = None
            self._timeout.cancel()
            self._timeout = None

    def add_task(self, func, args=None):
        if func and self._connection is None:
            Thread(target=self._connect, daemon=False).start()
        try:
            if not func:
                self.q.put((None, None), block=False)
            else:
                self.q.put((func, args), block=False)
        except Full:
            messagebox.showwarning("Queue is full", "The queue is full. Try again later.")

    def _do_work(self):
        while not self._quitting:
            func, data = self.q.get(block=True)  # wait until something is available
            self._running = True
            if func is None:
                if self._timeout:
                    self._timeout.cancel()
                    self._timeout = None
                self.q.task_done()
                self._running = False
                return

            while self._connection is None and not self._abort:  # suspend thread until there is an connection
                # print("waiting for connection")
                sleep(0.3)
            if self._abort:
                continue

            if data:
                try:
                    func(self._connection, *data)
                    self.q.task_done()
                except SocketDisconnectError:
                    messagebox.showerror("Connection Error", "Lost Connection.")
                    self.q.task_done()
                    self.disconnect()
                except Exception as e:
                    print("Unexpected Error:", type(e), str(e))
                    messagebox.showerror("Unexpected Error", "%s" % str(e) if str(e) else type(e))
                    self.q.task_done()
                    self.disconnect()
            else:
                try:
                    func(self._connection)
                    self.q.task_done()
                except Exception as e:
                    print(e)
                    self.q.task_done()
                    self.disconnect()

            self._running = False

            self.check_idle(True)

    def _connect(self):
        self._abort = False
        if self.parent_ui:
            self.parent_ui.progress.configure(mode="indeterminate", maximum=100)
            self.parent_ui.progress.start()
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
                self._abort = True
                messagebox.showerror("Connection Error", "Connection timeout on login.")
            except Exception as e:
                print(type(e), e.args, str(e))
                self._abort = True
                messagebox.showerror("Connection Error", "Could not establish a connection.\n%s" % e)
            finally:
                if self.parent_ui:
                    self.parent_ui.progress.stop()
                    self.parent_ui.progress.configure(value=0, mode="determinate")

        else:  # FTP
            try:
                ftp = FTP()
                ftp.encoding = self._enc
                ftp.connect(self._host, self._port, 10)
                ftp.login(self._name, self._passwd)

                self._connection = ftp
            except Exception as e:
                self._abort = True
                messagebox.showerror("Connection Error", str(e))
            finally:
                if self.parent_ui:
                    self.parent_ui.progress.stop()
                    self.parent_ui.progress.configure(value=0, mode="determinate")

    def disconnect(self):
        # print(self.name, "disconnect")
        self.q.queue.clear()
        if self._connection:
            try:
                if self._mode == "SFTP":
                    self._connection.session.disconnect()
                else:
                    self._connection.quit()
            except:
                pass
        self._connection = None

    def quit(self):
        self.q.queue.clear()
        self._quitting = True
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
