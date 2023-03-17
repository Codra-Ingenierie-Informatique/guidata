# -*- coding: utf-8 -*-
#
# Copyright © 2012 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guidata/__init__.py for details)

"""Little translation test"""


from guidata.config import _
from guidata.env import execenv

SHOW = False  # Do not show test in GUI-based test launcher

translations = (_("Some required entries are incorrect"),)


def test():
    for text in translations:
        execenv.print(text)
    execenv.print("OK")


if __name__ == "__main__":
    test()
