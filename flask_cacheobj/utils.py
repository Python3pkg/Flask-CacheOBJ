# -*- coding: utf-8 -*-

import inspect
from decorator import decorate

def make_deco(deco, **kwargs):
    def decorater(f):
        for key, value in list(kwargs.items()):
            setattr(f, key, value)
        return decorate(f, deco)
    return decorater
