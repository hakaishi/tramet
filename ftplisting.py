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


from os.path import basename


def ftp_file_list(conn, path):
    dir_res = []
    conn.dir(path, dir_res.append)
    nlst_res = conn.nlst(path)

    result = {}
    rdir = sorted(dir_res, key=lambda x: (x.lower(), len(x)))
    for f in sorted(nlst_res, key=lambda x: (x.lower(), len(x))):
        fn = basename(f)
        for i in range(len(rdir)):
            if rdir[i][0] != "l" and fn == rdir[i][-len(fn):]:
                result[fn] = rdir[i][:-len(fn)]
                del rdir[i]
                break
            elif rdir[i][0] == "l" and fn in rdir[i]:
                file = rdir[i].find(fn + " -> ")
                if file >= 0:
                    result[fn] = rdir[i][:file - 1]
                    del rdir[i]
                    break
    return result
