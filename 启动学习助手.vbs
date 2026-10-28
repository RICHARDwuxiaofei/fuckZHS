Option Explicit
Dim shell, files, root, python, entry
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
python = files.BuildPath(root, ".venv-windows-build\Scripts\pythonw.exe")
entry = files.BuildPath(root, "owner_entry.py")
If Not files.FileExists(python) Then
    MsgBox "The GUI virtual environment is missing. Please set up the source app first.", 48, "Learning Assistant"
    WScript.Quit 1
End If
shell.CurrentDirectory = root
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & entry & Chr(34), 0, False
