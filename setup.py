from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
build_options = {'packages': [], 'excludes': [],
                 "include_files": ["file.png", "folder.png", "link.png", "tramet.png"],
                 "build_exe": "build/tramet/"}

import sys
base = 'Win32GUI' if sys.platform == 'win32' else None
micon = "tramet.ico" if sys.platform == "win32" else "tramet.png"

executables = [
    Executable('main.py', base=base, targetName='tramet', icon=micon)
]

setup(name='Tramet',
      version = '1.0',
      description = 'SFTP/FTP client written in Python/tkinter',
      options = {'build_exe': build_options},
      executables = executables)
