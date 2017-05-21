# -*- coding: utf-8 -*-
"""
flask_cacheobj
~~~~~~~~~~~~~~

Flask-CacheOBJ Extension

:copyright: (c) 2016 Liwushuo Inc.
:license: MIT, see LICENSE for more details.
"""



from .api import CacheOBJ
FlaskCacheOBJ = CacheOBJ

from .msgpackable import Msgpackable, msgpackify

from .cache import (
    delete_cache,

    cache_obj,

    cache_hash,
    hash_del,

    cache_list,
    list_add,
    list_rem,
    list_len,

    exists,

    set_add,
    set_rem,
    set_len,

    cache_counter,
    inc_counter,
    dec_counter,
    get_counter,
    set_counter,
)
from .consts import __version__
