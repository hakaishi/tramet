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

from mttkinter.mtTkinter import *
from tkinter.ttk import *
from tkinter import StringVar, IntVar, BooleanVar, messagebox, filedialog

from Connection import Connection


class SearchView(Toplevel):
    """Dialog for searching files"""
    def __init__(self, root, current_path=""):
        """Constructor for SearchView

        :param root: the root parent Tk object
        :type root: Tk
        :param current_path: The default path to search in
        :type current_path: str
        """
        super().__init__(root)

        self.stop = False
        self.parent = root

        self.geometry("600x400")
        self.geometry("+%d+%d" % (root.winfo_x() + 50, root.winfo_y() + 25))
        self.minsize(550, 300)

        self.wm_title("Tramet - Search Files")

        pf = Labelframe(self, text="Path")
        pf.grid(sticky=EW, padx=5)

        self.path = StringVar(value=current_path)
        self.pathE = Entry(pf, textvariable=self.path)
        self.pathE.pack(fill=X, expand=True)

        rf = Labelframe(self, text="Recursive")
        rf.grid(sticky=EW, padx=5)

        self.recursive = BooleanVar(value=True)
        self.recursiveCB = Checkbutton(rf, text="Search recursive?", variable=self.recursive, command=self.setRecursive)
        self.recursiveCB.grid(row=0, sticky=EW)

        self.depthFrame = Frame(rf)
        Label(self.depthFrame, text="Max depth:").grid(row=0, column=0)
        self.depth = StringVar(value='1')
        self.depthS = Spinbox(self.depthFrame, from_=0, to=10, textvariable=self.depth)
        self.depthS.grid(row=0, column=1)
        self.depthFrame.grid(row=1, sticky=EW)

        sof = Labelframe(self, text="Search Options")
        sof.grid(sticky=EW, padx=5)

        Label(sof, text="File Name:").pack(fill=X, expand=True)
        self.filename = StringVar()
        self.filenameE = Entry(sof, textvariable=self.filename)
        self.filenameE.pack(fill=X, expand=True)

        self.sensitive = BooleanVar(value=False)
        self.sensitiveCB = Checkbutton(sof, text="Case sensitive?", variable=self.sensitive)
        self.sensitiveCB.pack(fill=X, expand=True)

        self.regex = BooleanVar(value=False)
        self.regexCB = Checkbutton(sof, text="Use Regular Expression?", variable=self.regex)
        self.regexCB.pack(fill=X, expand=True)

        btnf = Frame(self)
        btnf.grid(sticky=EW, padx=5)
        btnf.grid_columnconfigure(0, weight=1)
        btnf.grid_columnconfigure(1, weight=1)
        btnf.grid_rowconfigure(0, pad=15)

        self.searchBtn = Button(btnf, text="Search", command=self.search)
        self.searchBtn.grid(row=0, column=0)
        self.stopBtn = Button(btnf, text="Stop", command=self.do_stop)
        self.stopBtn.grid(row=0, column=1)

        scrollbar = Scrollbar(self, takefocus=0)
        self.box = Listbox(self, yscrollcommand=scrollbar.set, selectmode=EXTENDED, background="white smoke")
        self.box.grid(row=0, sticky=NSEW, column=1, rowspan=10)
        self.box.bind("<<ListboxSelect>>", self.on_selection_changed)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(9, weight=2)

        scrollbar.grid(row=0, column=2, sticky=NS, rowspan=10)
        scrollbar.config(command=self.box.yview)

        self.downloadBtn = Button(self, text="Download", state="disabled", command=self.download_selected)
        self.downloadBtn.grid(column=1)

        Sizegrip(self).grid(column=0, columnspan=3, sticky=E)

        self.worker = Connection(self.parent.mode, self.parent.enc, "")
        self.worker.connect(self.parent.mode, self.parent.connectionCB.get(), self.parent.port, self.parent.nameE.get(),
                            self.parent.password, self.parent.enc, "")

    def setRecursive(self):
        """Trigger recursive search"""
        if self.recursive.get():
            self.depthFrame.grid()
        else:
            self.depthFrame.grid_remove()

    def search(self):
        """Clear previous results and start to search with entered conditions"""
        self.box.delete(0, END)

        def insert_result(result):
            """callback to insert results"""
            self.box.insert(END, result)

        def done():
            """callback to show that search is done"""
            messagebox.showinfo("DONE", "Search completed!\nFound %d files." % len(self.box.get(0, END)),
                                parent=self)

        if not self.path.get() or not self.filename.get():
            if not self.path.get():
                messagebox.showwarning("No search path!", "Please specify a path to search in.", parent=self)
            else:
                messagebox.showwarning("No search pattern!", "Please specify a pattern to search.", parent=self)
        else:
            if self.regex.get() and self.filename.get()[0] in ["*", "+"]:
                messagebox.showwarning("Invalid search!", "Please insert a valid regular expression", parent=self)
                return

            self.worker.search(
                self.path.get(),
                self.recursive.get(),
                int(self.depth.get()),
                self.filename.get(),
                self.sensitive.get(),
                self.regex.get(),
                insert_result,
                done
            )

    def on_selection_changed(self, event=None):
        """allow download when more than one item is selected"""
        if len(self.box.curselection()) > 0:
            self.downloadBtn.configure(state="normal")
        else:
            self.downloadBtn.configure(state="disabled")

    def download_selected(self):
        """start download of selected files"""
        sel = self.box.curselection()

        dest = filedialog.askdirectory(title="Choose download destination", parent=self)

        def done(message=None):
            """callback for feedback about the download being done"""
            messagebox.showinfo("DONE", "Download done!", parent=self)

        for i in sel:
            pf = self.box.get(i)
            self.worker.download(self, pf, basename(pf), None, None, done, True, dest)

    def do_stop(self):
        """stop the current search"""
        self.stop = True
        self.worker.stop_search = True
        self.worker.disconnect()

    def destroy(self, event=None):
        """close and destroy the search dialog"""
        self.stop = True
        self.worker.stop_search = True
        self.parent.search_open = False
        self.parent.search_window = None
        self.worker.quit()
        super().destroy()


if __name__ == "__main__":
    rt = Tk()
    sv = SearchView(rt, "test")
    rt.withdraw()
    rt.wait_window(sv)
