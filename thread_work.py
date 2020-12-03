#!/usr/bin/env python
# -*- encoding=utf8 -*-

from threading import Thread, Timer, Lock
from queue import Queue, Full, Empty
from time import sleep

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ssh2.exceptions import *
from ftplib import FTP

from tkinter import messagebox


class ThreadWork:
    """Class to create and control a network related thread"""
    def __init__(self, mode, host, port, name, password, enc, timeout=10, descr="ThreadWork", max_size=10, ui=None):
        """
        ThreaWork constructor

        :param mode: connection mode sftp/ftp
        :type mode: str
        :param host: remote host name/ip
        :type host: str
        :param port: port for remote host
        :type port: int
        :param name: user name for remote host
        :type name: str
        :param password: password for remote user
        :type password: str
        :param enc: encoding for remote user
        :type enc: str
        :param timeout: login timeout. defaults to 10 seconds
        :type timeout: int
        :param descr: the name for the current thread object
        :type descr: str
        :param max_size: maximum default size for the queue
        :type max_size: int
        :param ui: parent Tk object
        :type ui: Tk"""
        self.name = descr
        self._quitting = False
        self.end = False
        self.lock = Lock()
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

        self.fileDescriptor = None

        self.parent_ui = ui

    def isConnected(self):
        """
        Check if the connection is still alive

        :return: bool
        """
        return self._connection is not None

    def check_idle(self, not_timeout=False):
        """check if the connection is no longer used and disconnect. Check every 30 seconds

        :param not_timeout: check ff check_idle is triggered by the timer
        :type not_timeout: bool
        """
        if self._timeout is None and self._connection is not None:
            self._timeout = Timer(30, self.check_idle)
            self._timeout.start()
            return
        if (not_timeout or self._running) and self._connection is not None:
            self._timeout.cancel()
            del self._timeout
            self._timeout = Timer(30, self.check_idle)
            self._timeout.start()
            return
        if self._connection is not None or (not self._running and not not_timeout):
            self.disconnect()

    def add_task(self, func, args=None):
        """add a task for the current connection and create a connection if necessary

        :param func: the function to be executed on this thread
        :type func: any
        :param args: arguments to be passed to the function object
        :type args: list of arguments
        """
        #: :param args:
        if func and self._connection is None:
            Thread(target=self._connect, daemon=True).start()
        try:
            if not func:
                self.q.put((None, None), block=False)
            else:
                self.q.put((func, args), block=False)
        except Full:
            messagebox.showwarning("Queue is full", "The queue is full. Try again later.")

    def _do_work(self):
        """check and wait for a connection and then execute the function with given parameters"""
        while not self._quitting:
            try:
                func, data = self.q.get(block=False)
            except Empty:
                sleep(0.1)
                continue

            while self._connection is None and not self._abort and not self._quitting:  # suspend thread until there is an connection
                # print("waiting for connection")
                sleep(0.3)
                continue
            
            if self._quitting:
                self.q.queue.clear()
                try:
                    self.q.task_done()
                except:
                    pass
                break

            if self._abort:
                self.q.task_done()
                continue

            self._running = True

            if data:
                try:
                    func(self._connection, *data)
                except SocketDisconnectError:
                    with self.lock:
                        print("disconnect error")
                    if not self._quitting:
                        messagebox.showerror("Connection Error", "Lost Connection.")
                        self.disconnect()
                except Exception as e:
                    with self.lock:
                        print("Unexpected Error:", type(e), str(e))
                    if not self._quitting:
                        messagebox.showerror("Unexpected Error", "%s" % str(e) if str(e) else type(e))
                        self.disconnect()
            else:
                try:
                    func(self._connection)
                except Exception as e:
                    if self.fileDescriptor:
                        self.fileDescriptor.close()
                        self.fileDescriptor = None
                    with self.lock:
                        print("exception ftp")
                        print(e)
                    if not self._quitting:
                        self.disconnect()
                        
            self.q.task_done()

            self._running = False

            if not self._quitting:
                self.check_idle(True)

        self.end = True

    def _connect(self):
        """create a connection for this thread"""
        self._abort = False
        size_bk = 0
        if self.parent_ui:
            size_bk += self.parent_ui.progress["maximum"]
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
            except AuthenticationError as e:
                self._abort = True
                messagebox.showerror("Authentication Error", "Wrong login credentials.")
            except Exception as e:
                print(type(e), e.args, str(e))
                self._abort = True
                messagebox.showerror("Connection Error", "Could not establish a connection.\n%s" % e)
            finally:
                if self.parent_ui:
                    self.parent_ui.progress.stop()
                    self.parent_ui.progress.configure(value=0, mode="determinate", maximum=size_bk)

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
                    self.parent_ui.progress.configure(value=0, mode="determinate", maximum=size_bk)

    def disconnect(self, quit=False):
        """stop and clear this thread. disconnect when necessary."""
        if not self._quitting:
            self._quitting = quit
        else:
            return
        if self._timeout:
            self._timeout.cancel()
            self._timeout = None
        self.q.queue.clear()
        if self.fileDescriptor:
            self.fileDescriptor.close()
            self.fileDescriptor = None
        if self._connection:
            try:
                if self._mode == "SFTP":
                    self._connection.session.disconnect()
                else:
                    # don't wait for timeout, just close connection
                    self._connection.close()
            except Exception as e:
                print("quit execption")
                print(e)
        self._connection = None


def singleShot(func, args=None):
    """single shot thread to execute a single task

    :param func: function object to be executed
    :type func: function
    :param args: arguments to be passed to the given function
    :type args: list of arguments
    """
    if args is None:
        args = []
    t = Thread(target=func, args=args, daemon=False)
    t.start()


__all__ = ['ThreadWork', 'singleShot']
