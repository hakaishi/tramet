#!/usr/bin/env python
# -*- encoding=utf8 -*-

import stat
from sys import exit
from time import sleep
from threading import Timer
from os.path import getmtime

from paramiko import SSHClient, AutoAddPolicy


cli = SSHClient()
cli.set_missing_host_key_policy(AutoAddPolicy())
# cli.connect("192.168.1.8", 2222, "test", "test", allow_agent=False)
cli.connect("localhost", 22, "chris", "korune", allow_agent=False)

# res = cli.exec_command("ls -R test/テスト".encode("sjis"))

# print(res[1].read().decode("sjis"))
sftp = cli.open_sftp()
# sftp.chmod("test/テスト/test", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO, encoding="sjis")
# l = sftp.rename("test/Xテンプレート/test", "test/Xテンプレート/test1", "sjis")
# print(sftp.stat("test/テスト/test", encoding="sjis"))
# with sftp.open("test/Xテンプレート/test1", "r", encoding="sjis") as f:
#     # print(f.read())
#     f.write("テスト".encode("sjis"))
# sftp.put("ファイル.gif", "test/テスト/ファイル.gif", encoding="sjis")
# sftp.get("test/テスト/ファイル.gif", "ファイル.gif", encoding="sjis")
sftp.utime("/home/chris/Musik/file.svg", (getmtime("file.svg"), getmtime("file.svg")))
# l = sftp.listdir_attr("Musik", "utf8", "replace")
# for x in l:
#     print(x)
# print(l)

cli.close()
cli = None

t = Timer(0.5, exit)
t.start()
t.join()
