#!/usr/bin/env python
# -*- encoding=utf8 -*-

from threading import Thread
from queue import Queue
from time import sleep

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ftplib import FTP


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

    def add_task(self, func, args=None):
        self.q.put((func, args))

    def _do_work(self):
        while not self._quitting:
            func, data = self.q.get(block=True)  # wait until something is available
            if func is None:
                return

            if self._mode == "SFTP":
                sock = socket(AF_INET, SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((self._host, self._port))
                cli = Session()
                cli.set_timeout(15000)
                cli.handshake(sock)

                cli.userauth_password(self._name, self._passwd)
                self._connection = cli.sftp_init()

                cli.set_timeout(0)
            else:
                ftp = FTP()
                ftp.encoding = self._enc
                ftp.connect(self._host, self._port, 10)
                ftp.login(self._name, self._passwd)

                self._connection = ftp

            if data:
                try:
                    func(self._connection, *data)
                except Exception as e:
                    print(e)
            else:
                func(self._connection)

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
        self.add_task(None)  # stop loop
        if self._connection:
            if self._mode == "SFTP":
                self._connection.session.disconnect()
            else:
                self._connection.quit()


def singleShot(func, args=[]):
    t = Thread(target=func, args=args, daemon=False)
    t.start()


__all__ = ['ThreadWork', 'singleShot']
