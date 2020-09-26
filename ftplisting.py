#!/usr/bin/env python
# -*- encoding=utf8 -*-

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
