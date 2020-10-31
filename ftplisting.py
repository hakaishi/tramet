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
    """
    get real file names vs file info
    Problem1: there might be spaces in the name
    Problem2: there are link objects
    Work-around: first get real file name with NLST

    :param conn: a ftp connection object
    :param path: the path to get content
    :return: returns files vs file info dict
    """
    dir_res = []
    conn.dir(path, dir_res.append)
    nlst_res = conn.nlst(path)

    if len(dir_res) > 0:
        # there might be an additional output with a count of files
        if len(dir_res[0].split()) < 6:
            dir_res.pop(0)
        elif len(dir_res[-1].split()) < 6:
            dir_res.pop(-1)

    count = len(dir_res)

    if count != len(nlst_res):
        # new files might be created between calling DIR and NLST
        raise Exception("Results of DIR and NLST are of different length!")

    result = {}

    # remove path
    for i in range(count):
        nlst_res[i] = basename(nlst_res[i])

    # construct file name & file info
    for i in range(count):
        if dir_res[i][0] != "l" and nlst_res[i] == dir_res[i][-len(nlst_res[i]):]:
            result[nlst_res[i]] = dir_res[i][:-len(nlst_res[i])]
        elif dir_res[i][0] == "l":
            file = dir_res[i].find(nlst_res[i] + " -> ")
            if file >= 0 and nlst_res[i] == dir_res[i][file:file+len(nlst_res[i])]:
                result[nlst_res[i]] = dir_res[i][:file - 1]  # subtract a white space
            else:
                # file names might not match because of sorting etc
                raise Exception("Results of DIR AND NLST do not match!")

    return result
