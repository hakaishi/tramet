from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
build_options = {'packages': [], 'excludes': [],
                 "include_files": ["file.png", "folder.png", "link.png"],
                 "build_exe": "build/tramet/"}

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('main.py', base=base, targetName = 'tramet')
]

setup(name='Tramet',
      version = '1.0',
      description = 'SFTP/FTP client written in Python/tkinter',
      options = {'build_exe': build_options},
      executables = executables)
