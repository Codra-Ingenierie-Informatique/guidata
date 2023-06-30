# -*- coding: utf-8 -*-
#
# Copyright © 2009-2011 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guidata/__init__.py for details)

# pylint: disable=W0613

"""
disthelpers
-----------

The ``guidata.disthelpers`` module provides helper functions for Python
package distribution on Microsoft Windows platforms with ``py2exe`` or on
all platforms thanks to ``cx_Freeze``.
"""

import atexit
import importlib
import importlib.machinery
import inspect
import os
import os.path as osp
import shutil
import sys
import traceback
import warnings
from subprocess import PIPE, Popen

if os.name == "nt":
    try:
        import py2exe  # Patching distutils -- analysis:ignore

        PY2EXE_INSTALLED = True
    except ImportError:
        PY2EXE_INSTALLED = False

try:
    import cx_Freeze

    CX_FREEZE_INSTALLED = True

    # Workaround against duplicated ddl files
    # https://github.com/anthony-tuininga/cx_Freeze/issues/366
    # https://github.com/anthony-tuininga/cx_Freeze/pull/400
    def _CopyFile(self, source, target, copyDependentFiles, includeMode=False):
        normalizedSource = os.path.normcase(os.path.normpath(source))
        normalizedTarget = os.path.normcase(os.path.normpath(target))
        if normalizedTarget in self.filesCopied:
            return
        if normalizedSource == normalizedTarget:
            return
        self._RemoveFile(target)
        targetDir = os.path.dirname(target)
        self._CreateDirectory(targetDir)
        if not self.silent:
            sys.stdout.write("copying %s -> %s\n" % (source, target))
        shutil.copyfile(source, target)
        shutil.copystat(source, target)
        if includeMode:
            shutil.copymode(source, target)
        self.filesCopied[normalizedTarget] = None
        if copyDependentFiles and source not in self.finder.excludeDependentFiles:
            for source in self._GetDependentFiles(source):
                target = os.path.join(self.targetDir, os.path.basename(source))
                self._CopyFile(source, target, copyDependentFiles)

    from cx_Freeze import freezer

    freezer.Freezer._CopyFile = _CopyFile
except ImportError:
    CX_FREEZE_INSTALLED = False

# Local imports
from guidata.configtools import get_module_path


# ==============================================================================
# modules management
# ==============================================================================
def atexit_deletion(path):
    """
    Function to call each time user want to delete file/folder at script end. To use with atexit.register()

    :param path: the absolute path of the file/folder to delete
    :type path: str
    """

    # We check if path really exists
    if os.path.exists(path):
        # We check if path is a file or a folder to use the right command
        try:
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
        except:
            print("Error during deleting path {0}".format(path))
            traceback.print_exc()
        else:
            print("Path {0} deleting with success".format(path))
    else:
        print("file/folder {0} is not existing".format(path))


def get_package_data(name, extlist, exclude_dirs=[]):
    """
    Return data files for package *name* with extensions in *extlist*
    (search recursively in package directories)
    """
    assert isinstance(extlist, (list, tuple))
    flist = []
    # Workaround to replace os.path.relpath (not available until Python 2.6):
    offset = len(name) + len(os.pathsep)
    for dirpath, _dirnames, filenames in os.walk(name):
        if dirpath not in exclude_dirs:
            for fname in filenames:
                if osp.splitext(fname)[1].lower() in extlist:
                    flist.append(osp.join(dirpath, fname)[offset:])
    return flist


def get_subpackages(name):
    """Return subpackages of package *name*"""
    splist = []
    for dirpath, _dirnames, _filenames in os.walk(name):
        if osp.isfile(osp.join(dirpath, "__init__.py")):
            splist.append(".".join(dirpath.split(os.sep)))
    return splist


def cythonize_all(relpath):
    """Cythonize all Cython modules in relative path"""
    from Cython.Compiler import Main

    for fname in os.listdir(relpath):
        if osp.splitext(fname)[1] == ".pyx":
            Main.compile(osp.join(relpath, fname))


# This is a list of module extensions (.pyd, .cp36-win_amd64.pyd, ...)
# used to detect if a filename refers to a module
# and to get the module from the filename.
# The list is sorted by length in descending order
# so that .cp36-win64.pyd like extensions are tested before .pyd.
_MODULE_SUFFIXES = importlib.machinery.all_suffixes()
_MODULE_SUFFIXES.sort(key=len, reverse=True)


# ==============================================================================
# Dependency management
# ==============================================================================
def get_changeset(path, rev=None):
    """Return Mercurial repository *path* revision number"""
    args = ["hg", "parent"]
    if rev is not None:
        args += ["--rev", str(rev)]
    process = Popen(args, stdout=PIPE, stderr=PIPE, cwd=path, shell=True)
    try:
        return process.stdout.read().splitlines()[0].split()[1]
    except IndexError:
        raise RuntimeError(process.stderr.read())


def prepend_module_to_path(module_path):
    """
    Prepend to sys.path module located in *module_path*
    Return string with module infos: name, revision, changeset

    Use this function:
    1) In your application to import local frozen copies of internal libraries
    2) In your py2exe distributed package to add a text file containing the returned string
    """
    if not osp.isdir(module_path):
        # Assuming py2exe distribution
        return
    sys.path.insert(0, osp.abspath(module_path))
    changeset = get_changeset(module_path)
    name = osp.basename(module_path)
    prefix = "Prepending module to sys.path"
    message = prefix + ("%s [revision %s]" % (name, changeset)).rjust(
        80 - len(prefix), "."
    )
    print(message, file=sys.stderr)
    if name in sys.modules:
        sys.modules.pop(name)
        nbsp = 0
        for modname in sys.modules.keys():
            if modname.startswith(name + "."):
                sys.modules.pop(modname)
                nbsp += 1
        warning = "(removed %s from sys.modules" % name
        if nbsp:
            warning += " and %d subpackages" % nbsp
        warning += ")"
        print(warning.rjust(80), file=sys.stderr)
    return message


def prepend_modules_to_path(module_base_path):
    """Prepend to sys.path all modules located in *module_base_path*"""
    if not osp.isdir(module_base_path):
        # Assuming py2exe distribution
        return
    fnames = [osp.join(module_base_path, name) for name in os.listdir(module_base_path)]
    messages = [
        prepend_module_to_path(dirname) for dirname in fnames if osp.isdir(dirname)
    ]
    return os.linesep.join(messages)


# ==============================================================================
# Distribution helpers
# ==============================================================================
def _remove_later(fname):
    """Try to remove file later (at exit)"""

    def try_to_remove(fname):
        if osp.exists(fname):
            os.remove(fname)

    atexit.register(try_to_remove, osp.abspath(fname))


def get_msvc_version(python_version):
    """Return Microsoft Visual C++ version used to build this Python version"""
    if python_version is None:
        python_version = "%s.%s" % (sys.version_info.major, sys.version_info.minor)
        warnings.warn("Assuming Python %s target" % python_version)
    if python_version in ("2.6", "2.7", "3.0", "3.1", "3.2"):
        # Python 2.6-2.7, 3.0-3.2 were built with Visual Studio 9.0.21022.8
        # (i.e. Visual C++ 2008, not Visual C++ 2008 SP1!)
        return "9.0.21022.8"
    elif python_version in ("3.3", "3.4"):
        # Python 3.3+ were built with Visual Studio 10.0.30319.1
        # (i.e. Visual C++ 2010)
        return "10.0"
    elif python_version in ("3.5", "3.6"):
        # Python 3.5+ were built with Visual Studio 14
        # (i.e. Visual Studio 2015)
        return "14.0"
    # TODO : Add missing python versions
    else:
        raise RuntimeError("Unsupported Python version %s" % python_version)


def get_dll_architecture(path):
    """Return DLL architecture (32 or 64bit) using Microsoft dumpbin.exe"""
    os.environ[
        "PATH"
    ] += r";C:\Program Files (x86)\Microsoft Visual Studio 9.0\Common7\IDE\;C:\Program Files (x86)\Microsoft Visual Studio 9.0\VC\BIN;C:\Program Files (x86)\Microsoft Visual Studio 10.0\Common7\IDE\;C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\BIN"
    process = Popen(
        ["dumpbin", "/HEADERS", osp.basename(path)],
        stdout=PIPE,
        stderr=PIPE,
        cwd=osp.dirname(path),
        shell=True,
    )
    output = process.stdout.read()
    error = process.stderr.read()
    if error:
        raise RuntimeError(error)
    elif "x86" in output:
        return 32
    elif "x64" in output:
        return 64
    else:
        raise ValueError("Unable to get DLL architecture")


def get_msvc_dlls(msvc_version, architecture=None, check_architecture=False):
    """Get the list of Microsoft Visual C++ DLLs associated to
    architecture and Python version, create the manifest file.

    architecture: integer (32 or 64) -- if None, take the Python build arch
    python_version: X.Y"""
    current_architecture = 64 if sys.maxsize > 2**32 else 32
    if architecture is None:
        architecture = current_architecture
    assert architecture in (32, 64)

    filelist = []

    msvc_major = msvc_version.split(".")[0]
    msvc_minor = msvc_version.split(".")[1]

    if msvc_major == "9":
        key = "1fc8b3b9a1e18e3b"
        atype = "" if architecture == 64 else "win32"
        arch = "amd64" if architecture == 64 else "x86"

        groups = {
            "CRT": ("msvcr90.dll", "msvcp90.dll", "msvcm90.dll"),
            #                  'OPENMP': ('vcomp90.dll',)
        }

        for group, dll_list in groups.items():
            dlls = ""
            for dll in dll_list:
                dlls += '    <file name="%s" />%s' % (dll, os.linesep)

            manifest = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <!-- Copyright (c) Microsoft Corporation.  All rights reserved. -->
            <assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
                <noInheritable/>
                <assemblyIdentity
                    type="%(atype)s"
                    name="Microsoft.VC90.%(group)s"
                    version="%(version)s"
                    processorArchitecture="%(arch)s"
                    publicKeyToken="%(key)s"
                />
            %(dlls)s</assembly>
            """ % dict(
                version=msvc_version,
                key=key,
                atype=atype,
                arch=arch,
                group=group,
                dlls=dlls,
            )

            vc90man = "Microsoft.VC90.%s.manifest" % group
            open(vc90man, "w").write(manifest)
            _remove_later(vc90man)
            filelist += [vc90man]

            winsxs = osp.join(os.environ["windir"], "WinSxS")
            vcstr = "%s_Microsoft.VC90.%s_%s_%s" % (arch, group, key, msvc_version)
            for fname in os.listdir(winsxs):
                path = osp.join(winsxs, fname)
                if osp.isdir(path) and fname.lower().startswith(vcstr.lower()):
                    for dllname in os.listdir(path):
                        filelist.append(osp.join(path, dllname))
                    break
            else:
                raise RuntimeError(
                    "Microsoft Visual C++ %s DLLs version %s "
                    "were not found" % (group, msvc_version)
                )

    elif msvc_major == "10":
        namelist = [
            name % (msvc_major + msvc_minor)
            for name in (
                "msvcp%s.dll",
                "msvcr%s.dll",
                "vcomp%s.dll",
            )
        ]

        windir = os.environ["windir"]
        is_64bit_windows = osp.isdir(osp.join(windir, "SysWOW64"))

        # Reminder: WoW64 (*W*indows 32-bit *o*n *W*indows *64*-bit) is a
        # subsystem of the Windows operating system capable of running 32-bit
        # applications and is included on all 64-bit versions of Windows
        # (source: http://en.wikipedia.org/wiki/WoW64)
        #
        # In other words, "SysWOW64" contains 32-bit DLL and applications,
        # whereas "System32" contains 64-bit DLL and applications on a 64-bit
        # system.
        if architecture == 64:
            # 64-bit DLLs are located in...
            if is_64bit_windows:
                sysdir = "System32"  # on a 64-bit OS
            else:
                # ...no directory to be found!
                raise RuntimeError("Can't find 64-bit DLLs on a 32-bit OS")
        else:
            # 32-bit DLLs are located in...
            if is_64bit_windows:
                sysdir = "SysWOW64"  # on a 64-bit OS
            else:
                sysdir = "System32"  # on a 32-bit OS

        for dllname in namelist:
            fname = osp.join(windir, sysdir, dllname)
            if osp.exists(fname):
                filelist.append(fname)
            else:
                raise RuntimeError(
                    "Microsoft Visual C++ DLLs version %s "
                    "were not found" % msvc_version
                )

    else:
        raise RuntimeError("Unsupported MSVC version %s" % msvc_version)

    if check_architecture:
        for path in filelist:
            if path.endswith(".dll"):
                try:
                    arch = get_dll_architecture(path)
                except RuntimeError:
                    return
                if arch != architecture:
                    raise RuntimeError(
                        "%s: expecting %dbit, found %dbit" % (path, architecture, arch)
                    )

    return filelist


def create_msvc_data_files(architecture=None, python_version=None, verbose=False):
    """Including Microsoft Visual C++ DLLs"""
    msvc_version = get_msvc_version(python_version)
    filelist = get_msvc_dlls(msvc_version, architecture=architecture)
    print(create_msvc_data_files.__doc__)
    if verbose:
        for name in filelist:
            print("  ", name)
    msvc_major = msvc_version.split(".")[0]
    if msvc_major == "9":
        return [
            ("Microsoft.VC90.CRT", filelist),
        ]
    else:
        return [
            ("", filelist),
        ]


def to_include_files(data_files):
    """Convert data_files list to include_files list

    data_files:
      * this is the ``py2exe`` data files format
      * list of tuples (dest_dirname, (src_fname1, src_fname2, ...))

    include_files:
      * this is the ``cx_Freeze`` data files format
      * list of tuples ((src_fname1, dst_fname1),
                        (src_fname2, dst_fname2), ...))
    """
    include_files = []
    for dest_dir, fnames in data_files:
        for source_fname in fnames:
            dest_fname = osp.join(dest_dir, osp.basename(source_fname))
            include_files.append((source_fname, dest_fname))
    return include_files


def strip_version(version):
    """Return version number with digits only
    (Windows does not support strings in version numbers)"""
    return version.split("beta")[0].split("alpha")[0].split("rc")[0].split("dev")[0]


def remove_dir(dirname):
    """Remove directory *dirname* and all its contents
    Print details about the operation (progress, success/failure)"""
    print("Removing directory '%s'..." % dirname, end=" ")
    try:
        shutil.rmtree(dirname, ignore_errors=True)
        print("OK")
    except Exception:
        print("Failed!")
        traceback.print_exc()


class Distribution(object):
    """Distribution object

    Help creating an executable using ``py2exe`` or ``cx_Freeze``
    """

    DEFAULT_EXCLUDES = [
        "Tkconstants",
        "Tkinter",
        "tcl",
        "tk",
        "wx",
        "_imagingtk",
        "curses",
        "PIL._imagingtk",
        "ImageTk",
        "PIL.ImageTk",
        "FixTk",
        "bsddb",
        "email",
        "pywin.debugger",
        "pywin.debugger.dbgcon",
        "matplotlib",
    ]
    if sys.version_info.major == 2:
        #  Fixes compatibility issue with IPython (more specifically with one
        #  of its dependencies: `jsonschema`) on Python 2.7
        DEFAULT_EXCLUDES += ["collections.abc"]
    DEFAULT_INCLUDES = []
    DEFAULT_BIN_EXCLUDES = [
        "MSVCP100.dll",
        "MSVCP90.dll",
        "w9xpopen.exe",
        "MSVCP80.dll",
        "MSVCR80.dll",
    ]
    DEFAULT_BIN_INCLUDES = []
    DEFAULT_BIN_PATH_INCLUDES = []
    DEFAULT_BIN_PATH_EXCLUDES = []

    def __init__(self):
        self.name = None
        self.version = None
        self.description = None
        self.script = None
        self.target_name = None
        self._target_dir = None
        self.icon = None
        self.data_files = []
        self.includes = self.DEFAULT_INCLUDES
        self.excludes = self.DEFAULT_EXCLUDES
        self.bin_includes = self.DEFAULT_BIN_INCLUDES
        self.bin_excludes = self.DEFAULT_BIN_EXCLUDES
        self.bin_path_includes = self.DEFAULT_BIN_PATH_INCLUDES
        self.bin_path_excludes = self.DEFAULT_BIN_PATH_EXCLUDES
        self.msvc = os.name == "nt"
        self._py2exe_is_loaded = False
        self._pyqt_added = False
        self._pyside_added = False
        # Attributes relative to cx_Freeze:
        self.executables = []
        self.include_msvcr = False
        self.module_import_func_dict = {
            "PyQt5": self.add_pyqt,
            "PySide": self.add_pyside,
            "scipy": self.add_module_dir,
            "matplotlib": self.add_matplotlib,
            "h5py": self.add_h5py,
            "docutils": self.add_doc_module,
            "rst2pdf": self.add_doc_module,
            "sphinx": self.add_doc_module,
            "pygments": self.add_pygments,
            "zmq": self.add_zmq,
            "zmq": self.add_guidata,
        }

    @property
    def target_dir(self):
        """Return target directory (default: 'dist')"""
        dirname = self._target_dir
        if dirname is None:
            return "dist"
        else:
            return dirname

    @target_dir.setter  # analysis:ignore
    def target_dir(self, value):
        self._target_dir = value

    def setup(
        self,
        name,
        version,
        description,
        script,
        target_name=None,
        target_dir=None,
        icon=None,
        data_files=None,
        includes=None,
        excludes=None,
        bin_includes=None,
        bin_excludes=None,
        bin_path_includes=None,
        bin_path_excludes=None,
        msvc=None,
        include_msvcr=False,
    ):
        """Setup distribution object

        Notes:
          * bin_path_excludes is specific to cx_Freeze (ignored if it's None)
          * if msvc is None, it's set to True by default on Windows
            platforms, False on non-Windows platforms
        """
        self.name = name
        self.version = strip_version(version) if os.name == "nt" else version
        self.description = description
        assert osp.isfile(script)
        self.script = script
        self.target_name = target_name
        self.target_dir = target_dir
        self.icon = icon
        if data_files is not None:
            self.data_files += data_files
        if includes is not None:
            self.includes += includes
        if excludes is not None:
            self.excludes += excludes
        if bin_includes is not None:
            self.bin_includes += bin_includes
        if bin_excludes is not None:
            self.bin_excludes += bin_excludes
        if bin_path_includes is not None:
            self.bin_path_includes += bin_path_includes
        if bin_path_excludes is not None:
            self.bin_path_excludes += bin_path_excludes
        if msvc is not None:
            self.msvc = msvc
        if self.msvc:
            try:
                self.data_files += create_msvc_data_files()
            except IOError:
                print(
                    "Setting the msvc option to False " "will avoid this error",
                    file=sys.stderr,
                )
                raise
        self.include_msvcr = include_msvcr
        # cx_Freeze:
        self.add_executable(self.script, self.target_name, icon=self.icon)

    def add_text_data_file(self, filename, contents):
        """Create temporary data file *filename* with *contents*
        and add it to *data_files*"""
        open(filename, "wb").write(bytes(contents, "utf-8"))
        self.data_files += [("", (filename,))]
        atexit.register(atexit_deletion, os.path.abspath(filename))

    def add_data_file(self, filename, destdir=""):
        self.data_files += [(destdir, (filename,))]

    # ------ Adding packages
    def add_pyqt(self):
        """Include module PyQt5 to the distribution"""
        # TODO: Add PyQt6 support
        if self._pyqt_added:
            return
        self._pyqt_added = True

        import PyQt5 as PyQt

        qtver = 5
        self.includes += [
            "sip",
            f"PyQt{qtver}.Qt",
            f"PyQt{qtver}.QtSvg",
            f"PyQt{qtver}.QtNetwork",
        ]

        pyqt_path = osp.dirname(PyQt.__file__)

        # Configuring PyQt
        conf = os.linesep.join(["[Paths]", "Prefix = .", "Binaries = ."])
        self.add_text_data_file("qt.conf", conf)

        # Including plugins (.svg icons support, QtDesigner support, ...)
        if self.msvc:
            vc90man = "Microsoft.VC90.CRT.manifest"
            pyqt_tmp = "pyqt_tmp"
            if osp.isdir(pyqt_tmp):
                shutil.rmtree(pyqt_tmp)
            os.mkdir(pyqt_tmp)
            vc90man_pyqt = osp.join(pyqt_tmp, vc90man)
            if osp.isfile(vc90man):
                man = (
                    open(vc90man, "r")
                    .read()
                    .replace('<file name="', '<file name="Microsoft.VC90.CRT\\')
                )
                open(vc90man_pyqt, "w").write(man)
            else:
                vc90man_pyqt = None
        for dirpath, _, filenames in os.walk(osp.join(pyqt_path, "plugins")):
            filelist = [
                osp.join(dirpath, f)
                for f in filenames
                if osp.splitext(f)[1] in (".dll", ".py")
            ]
            if (
                self.msvc
                and vc90man_pyqt is not None
                and [f for f in filelist if osp.splitext(f)[1] == ".dll"]
            ):
                # Where there is a DLL build with Microsoft Visual C++ 2008,
                # there must be a manifest file as well...
                # ...congrats to Microsoft for this great simplification!
                filelist.append(vc90man_pyqt)
            self.data_files.append(
                (dirpath[len(pyqt_path) + len(os.pathsep) :], filelist)
            )
        if self.msvc:
            atexit.register(atexit_deletion, os.path.abspath(pyqt_tmp))

        # Including french translation
        fr_trans = osp.join(pyqt_path, "translations", "qt_fr.qm")
        if osp.exists(fr_trans):
            self.data_files.append(("translations", (fr_trans,)))

    def add_pyside(self):
        """Include module PySide to the distribution"""
        if self._pyside_added:
            return
        self._pyside_added = True

        self.includes += [
            "PySide.QtDeclarative",
            "PySide.QtHelp",
            "PySide.QtMultimedia",
            "PySide.QtNetwork",
            "PySide.QtOpenGL",
            "PySide.QtScript",
            "PySide.QtScriptTools",
            "PySide.QtSql",
            "PySide.QtSvg",
            "PySide.QtTest",
            "PySide.QtUiTools",
            "PySide.QtWebKit",
            "PySide.QtXml",
            "PySide.QtXmlPatterns",
        ]

        import PySide

        pyside_path = osp.dirname(PySide.__file__)

        # Configuring PySide
        conf = os.linesep.join(["[Paths]", "Prefix = .", "Binaries = ."])
        self.add_text_data_file("qt.conf", conf)

        # Including plugins (.svg icons support, QtDesigner support, ...)
        if self.msvc:
            vc90man = "Microsoft.VC90.CRT.manifest"
            os.mkdir("pyside_tmp")
            vc90man_pyside = osp.join("pyside_tmp", vc90man)
            man = (
                open(vc90man, "r")
                .read()
                .replace('<file name="', '<file name="Microsoft.VC90.CRT\\')
            )
            open(vc90man_pyside, "w").write(man)
        for dirpath, _, filenames in os.walk(osp.join(pyside_path, "plugins")):
            filelist = [
                osp.join(dirpath, f)
                for f in filenames
                if osp.splitext(f)[1] in (".dll", ".py")
            ]
            if self.msvc and [f for f in filelist if osp.splitext(f)[1] == ".dll"]:
                # Where there is a DLL build with Microsoft Visual C++ 2008,
                # there must be a manifest file as well...
                # ...congrats to Microsoft for this great simplification!
                filelist.append(vc90man_pyside)
            self.data_files.append(
                (dirpath[len(pyside_path) + len(os.pathsep) :], filelist)
            )

        # Replacing dlls found by cx_Freeze by the real PySide Qt dlls:
        # (http://qt-project.org/wiki/Packaging_PySide_applications_on_Windows)
        dlls = [
            osp.join(pyside_path, fname)
            for fname in os.listdir(pyside_path)
            if osp.splitext(fname)[1] == ".dll"
        ]
        self.data_files.append(("", dlls))

        if self.msvc:
            atexit.register(remove_dir, "pyside_tmp")

        # Including french translation
        fr_trans = osp.join(pyside_path, "translations", "qt_fr.qm")
        if osp.exists(fr_trans):
            self.data_files.append(("translations", (fr_trans,)))

    def add_qt_bindings(self):
        """Include Qt bindings, i.e. PyQt or PySide"""
        try:
            importlib.find_module("PyQt5")
            self.add_modules("PyQt5")
        except ImportError:
            self.add_modules("PySide")

    def add_matplotlib(self):
        """Include module Matplotlib to the distribution"""
        if "matplotlib" in self.excludes:
            self.excludes.remove("matplotlib")
        try:
            import matplotlib.numerix  # analysis:ignore

            self.includes += [
                "matplotlib.numerix.ma",
                "matplotlib.numerix.fft",
                "matplotlib.numerix.linear_algebra",
                "matplotlib.numerix.mlab",
                "matplotlib.numerix.random_array",
            ]
        except ImportError:
            pass
        self.add_module_data_files(
            "matplotlib",
            ("mpl-data",),
            (
                ".conf",
                ".glade",
                "",
                ".png",
                ".svg",
                ".xpm",
                ".ppm",
                ".npy",
                ".afm",
                ".ttf",
            ),
        )

    def add_h5py(self):
        self.add_module_dir("h5py")
        if self.bin_path_excludes is not None and os.name == "nt":
            # Specific to cx_Freeze on Windows: avoid including a zlib dll
            # built with another version of Microsoft Visual Studio
            self.bin_path_excludes += [
                r"C:\Program Files",
                r"C:\Program Files (x86)",
            ]
            self.data_files.append(  # necessary for cx_Freeze only
                ("", (osp.join(get_module_path("h5py"), "zlib1.dll"),))
            )

    def add_doc_module(self, module_name):
        self.includes += [
            "docutils.writers.null",
            "docutils.languages.en",
            "docutils.languages.fr",
        ]
        if module_name == "rst2pdf":
            self.add_module_data_files(
                "rst2pdf", ("styles",), (".json", ".style"), copy_to_root=True
            )
        if module_name == "sphinx":
            import sphinx.ext

            for fname in os.listdir(osp.dirname(sphinx.ext.__file__)):
                if osp.splitext(fname)[1] == ".py":
                    modname = "sphinx.ext.%s" % osp.splitext(fname)[0]
                    self.includes.append(modname)

    def add_pygments(self):
        self.includes += [
            "pygments",
            "pygments.formatters",
            "pygments.lexers",
            "pygments.lexers.agile",
        ]

    def add_zmq(self):
        # FIXME: this is not working, yet... (missing DLL)
        self.includes += [
            "zmq",
            "zmq.core._poll",
            "zmq.core._version",
            "zmq.core.constants",
            "zmq.core.context",
            "zmq.core.device",
            "zmq.core.error",
            "zmq.core.message",
            "zmq.core.socket",
            "zmq.core.stopwatch",
        ]
        if os.name == "nt":
            self.bin_includes += ["libzmq.dll"]

    def add_guidata(self):
        self.add_module_data_files(
            "guidata", ("images",), (".png", ".svg"), copy_to_root=False
        )
        self.add_qt_bindings()

    def add_modules(self, *module_names):
        """Include module *module_name*"""
        # TODO: Add support for PyQt6
        for module_name in module_names:
            print(f"Configuring module '{module_name}'")
            if module_name in self.module_import_func_dict.keys():
                func = self.module_import_func_dict[module_name]
                if not inspect.getargspec().args:
                    func()
                else:
                    func(module_name)
            else:
                try:
                    # Modules based on the same scheme as guidata and guiqwt
                    self.add_module_data_files(
                        module_name, ("images",), (".png", ".svg"), copy_to_root=False
                    )
                except IOError:
                    raise RuntimeError(f"Module not supported:{module_name}")
            # XXX: guiqwt ref, delete ?
            # if module_name == "guiqwt":
            #     self.add_module_data_files(
            #         "guiqwt", ("images",), (".png", ".svg"), copy_to_root=False
            #     )
            #     if os.name == "nt":
            #         # Specific to cx_Freeze: including manually MinGW DLLs
            #         self.bin_includes += ["libgcc_s_dw2-1.dll", "libstdc++-6.dll"]

    def add_module_data_dir(
        self,
        module_name,
        data_dir_name,
        extensions,
        copy_to_root=True,
        verbose=False,
        exclude_dirs=[],
    ):
        """
        Collect data files in *data_dir_name* for module *module_name*
        and add them to *data_files*
        *extensions*: list of file extensions, e.g. ('.png', '.svg')
        """
        module_dir = get_module_path(module_name)
        nstrip = len(module_dir) + len(osp.sep)
        data_dir = osp.join(module_dir, data_dir_name)
        if not osp.isdir(data_dir):
            raise IOError(f"Directory not found: {data_dir}")
        for dirpath, _dirnames, filenames in os.walk(data_dir):
            dirname = dirpath[nstrip:]
            if osp.basename(dirpath) in exclude_dirs:
                continue
            if not copy_to_root:
                dirname = osp.join(module_name, dirname)
            pathlist = [
                osp.join(dirpath, f)
                for f in filenames
                if osp.splitext(f)[1].lower() in extensions
            ]
            self.data_files.append((dirname, pathlist))
            if verbose:
                for name in pathlist:
                    print("  ", name)

    def add_module_dir(self, module_name, verbose=False, exclude_dirs=[]):
        """
        Collect all module files for module *module_name*
        and add them to *data_files*
        """
        module_dir = get_module_path(module_name)
        nstrip = len(module_dir) + len(osp.sep)
        for dirpath, dirnames, filenames in os.walk(module_dir):
            if osp.basename(dirpath) in exclude_dirs:
                continue
            for dn in dirnames[:]:
                if not osp.isfile(osp.join(dirpath, dn, "__init__.py")):
                    dirnames.remove(dn)
            dirname = osp.join(module_name, dirpath[nstrip:])
            for filename in filenames:
                ext = osp.splitext(filename)[1].lower()
                if ext in (".py", ".pyd"):
                    if filename == "__init__.py":
                        fn = dirname
                    else:
                        for suffix in _MODULE_SUFFIXES:
                            if filename.endswith(suffix):
                                fn = osp.join(dirname, filename[: -len(suffix)])
                                break
                    if fn.endswith(os.sep):
                        fn = fn[:-1]
                    modname = ".".join(fn.split(os.sep))
                    self.includes += [modname]
                    if verbose:
                        print("  + ", modname)

    def add_module_data_files(
        self,
        module_name,
        data_dir_names,
        extensions,
        copy_to_root=True,
        verbose=False,
        exclude_dirs=[],
    ):
        """
        Collect data files for module *module_name* and add them to *data_files*
        *data_dir_names*: list of dirnames, e.g. ('images', )
        *extensions*: list of file extensions, e.g. ('.png', '.svg')
        """
        print(
            "Adding module '{}' data files in {} ({})".format(
                module_name,
                ", ".join(data_dir_names),
                ", ".join(extensions),
            )
        )
        module_dir = get_module_path(module_name)
        for data_dir_name in data_dir_names:
            self.add_module_data_dir(
                module_name,
                data_dir_name,
                extensions,
                copy_to_root,
                verbose,
                exclude_dirs,
            )
        translation_file = osp.join(
            module_dir, "locale", "fr", "LC_MESSAGES", f"{module_name}.mo"
        )
        if osp.isfile(translation_file):
            self.data_files.append(
                (
                    osp.join(module_name, "locale", "fr", "LC_MESSAGES"),
                    (translation_file,),
                )
            )
            print(
                "Adding module '{}' translation file: {}".format(
                    module_name,
                    osp.basename(translation_file),
                )
            )

    def build(self, library, cleanup=True, create_archive=None):
        """Build executable with given library.

        library:
            * 'py2exe': deploy using the `py2exe` library
            * 'cx_Freeze': deploy using the `cx_Freeze` library

        cleanup: remove 'build/dist' directories before building distribution

        create_archive (requires the executable `zip`):
            * None or False: do nothing
            * 'add': add target directory to a ZIP archive
            * 'move': move target directory to a ZIP archive
        """
        if library == "py2exe":
            self.build_py2exe(cleanup=cleanup, create_archive=create_archive)
        elif library == "cx_Freeze":
            self.build_cx_freeze(cleanup=cleanup, create_archive=create_archive)
        else:
            raise RuntimeError("Unsupported library %s" % library)

    def __cleanup(self):
        """Remove old build and dist directories"""
        remove_dir("build")
        if osp.isdir("dist"):
            remove_dir("dist")
        remove_dir(self.target_dir)

    def __create_archive(self, option):
        """Create a ZIP archive

        option:
            * 'add': add target directory to a ZIP archive
            * 'move': move target directory to a ZIP archive
        """
        name = self.target_dir
        os.system(f'python -m zipfile -c "{name}.zip" "{name}"')
        if option == "move":
            shutil.rmtree(name)

    def build_py2exe(
        self,
        cleanup=True,
        compressed=2,
        optimize=2,
        company_name=None,
        copyright=None,
        create_archive=None,
    ):
        """Build executable with py2exe

        cleanup: remove 'build/dist' directories before building distribution

        create_archive (requires the executable `zip`):
            * None or False: do nothing
            * 'add': add target directory to a ZIP archive
            * 'move': move target directory to a ZIP archive
        """
        if not PY2EXE_INSTALLED:
            raise RuntimeError(
                "You must install py2exe in order to build the executable"
            )

        from distutils.core import setup

        self._py2exe_is_loaded = True
        if cleanup:
            self.__cleanup()
        sys.argv += ["py2exe"]
        options = dict(
            compressed=compressed,
            optimize=optimize,
            includes=self.includes,
            excludes=self.excludes,
            dll_excludes=self.bin_excludes,
            dist_dir=self.target_dir,
        )
        windows = dict(
            name=self.name,
            description=self.description,
            script=self.script,
            icon_resources=[(0, self.icon)],
            bitmap_resources=[],
            other_resources=[],
            dest_base=osp.splitext(self.target_name)[0],
            version=self.version,
            company_name=company_name,
            copyright=copyright,
        )
        setup(
            data_files=self.data_files,
            windows=[
                windows,
            ],
            options=dict(py2exe=options),
        )
        if create_archive:
            self.__create_archive(create_archive)

    def add_executable(self, script, target_name, icon=None):
        """Add executable to the cx_Freeze distribution
        Not supported for py2exe"""
        if not CX_FREEZE_INSTALLED:
            return
        from cx_Freeze import Executable

        base = None
        if script.endswith(".pyw") and os.name == "nt":
            base = "win32gui"
        self.executables += [
            Executable(script, base=base, icon=icon, targetName=target_name)
        ]

    def build_cx_freeze(self, cleanup=True, create_archive=None):
        """Build executable with cx_Freeze

        cleanup: remove 'build/dist' directories before building distribution

        create_archive (requires the executable `zip`):
            * None or False: do nothing
            * 'add': add target directory to a ZIP archive
            * 'move': move target directory to a ZIP archive
        """
        if not CX_FREEZE_INSTALLED:
            raise RuntimeError(
                "You must install cx_Freeze in order to build the executable"
            )
        assert not self._py2exe_is_loaded, "cx_Freeze can't be executed after py2exe"
        # ===== Monkey-patching cx_Freeze (backported from v5.0 dev) ===========
        from cx_Freeze import hooks, setup

        def load_h5py(finder, module):
            """h5py module has a number of implicit imports"""
            finder.IncludeModule("h5py.defs")
            finder.IncludeModule("h5py.utils")
            finder.IncludeModule("h5py._proxy")
            try:
                import h5py.api_gen

                finder.IncludeModule("h5py.api_gen")
            except ImportError:
                pass
            finder.IncludeModule("h5py._errors")
            finder.IncludeModule("h5py.h5ac")

        hooks.load_h5py = load_h5py
        # ===== Monkey-patching cx_Freeze (backported from v5.0 dev) ===========

        # ===== Monkey-patching cx_Freeze for Scipy ============================
        def load_scipy(finder, module):
            pass

        hooks.load_scipy = load_scipy
        # ===== Monkey-patching cx_Freeze for Scipy ============================

        if cleanup:
            self.__cleanup()
        sys.argv += ["build"]
        excv = "3" if sys.version[0] == "2" else "2"
        self.excludes += [f"sympy.mpmath.libmp.exec_py{excv}"]
        self.excludes += [f"PyQt4.uic.port_v{excv}"]
        build_exe = dict(
            include_files=to_include_files(self.data_files),
            includes=self.includes,
            excludes=self.excludes,
            bin_excludes=self.bin_excludes,
            bin_includes=self.bin_includes,
            bin_path_includes=self.bin_path_includes,
            bin_path_excludes=self.bin_path_excludes,
            build_exe=self.target_dir,
            optimize=0,
            zip_include_packages="*",
            zip_exclude_packages=["numpy", "pandas"],
            include_msvcr=self.include_msvcr,
        )
        setup(
            name=self.name,
            version=self.version,
            description=self.description,
            executables=self.executables,
            options=dict(build_exe=build_exe),
        )
        if create_archive:
            self.__create_archive(create_archive)


if __name__ == "__main__":
    for python_version in ("2.7", "3.3"):
        for arch in (32, 64):
            print("Python %s %dbit" % (python_version, arch))
            msvc_version = get_msvc_version(python_version)
            filelist = get_msvc_dlls(msvc_version, architecture=arch)
            for fname in filelist:
                if ".dll" in fname:
                    print(get_dll_architecture(fname))
            print()