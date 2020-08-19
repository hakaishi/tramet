# Tramet
File Transfer App for FTP and SFTP written in Python / tkinter

### Dependencies
* Python 3
* mttkinter
* ssh2-python

### TODO:
* Download multiple files/folders (using a queue)
* File search
* Rework user management
* Show progress when down-/uploading
* translations ?

### Known Problems:
1. No efficient way to display user- and group names when using SSH
2. Implementation of MSLD (FTP) is too diverse and thus unusable
3. Display of user- and group names when using FTP depends on the FTP server and its settings.
4. Some FTP servers don't have a way to set the access/modification date of files after upload
5. Symbolic links are not supported.
6. There is some trouble with file uploads. Timestamps are not preserved yet. The issue is currently under research