#!/usr/bin/env python
# -*- encoding=utf8 -*-

from threading import Thread
from queue import Queue
from time import sleep

from socket import socket, AF_INET, SOCK_STREAM
from ssh2.session import Session
from ftplib import FTP


class ThreadWork:
    _quitting = False

    def __init__(self, mode, host, port, name, password, enc):
        self._mode = mode
        self._host = host
        self._port = port
        self._name = name
        self._passwd = password
        self._enc = enc
        self.q = Queue()
        self._thread = Thread(target=self._do_work, daemon=False)
        self._thread.start()

    def add_task(self, func, args=None):
        conn = None
        if self._mode == "SFTP":
            sock = socket(AF_INET, SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self._host, self._port))
            cli = Session()
            cli.set_timeout(15000)
            cli.handshake(sock)

            cli.userauth_password(self._name, self._passwd)
            conn = cli.sftp_init()

            cli.set_timeout(0)
        else:
            ftp = FTP()
            ftp.encoding = self._enc
            ftp.connect(self._host, self._port, 10)
            ftp.login(self._name, self._passwd)

            conn = ftp
        self.q.put((conn, func, args))

    def _do_work(self):
        while not self._quitting:
            if not self.q.empty():
                conn, func, data = self.q.get(False)
                if data:
                    print(func, conn, data)
                    try:
                        func(conn, *data)
                    except Exception as e:
                        print(e)
                else:
                    func(conn)
                self.q.task_done()
            else:
                sleep(0.3)

    def stop(self):
        self._quitting = True


__all__ = ['ThreadWork', ]
