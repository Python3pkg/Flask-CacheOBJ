# -*- coding: utf-8 -*-
"""
flask_cacheobj.cache
~~~~~~~~~~~~~~~~~~~~

Cache functions.

:copyright: (c) 2016 Liwushuo Inc.
:license: MIT, see LICENSE for more details.
"""

import inspect
import logging
from functools import wraps

import msgpack
from redis.exceptions import ConnectionError
from decorator import decorator, decorate

from .msgpackable import encode, decode
from .format import format_key_pattern
from .proxy import mc
from .utils import make_deco
from ._compat import text_type, integer_types
import collections

logger = logging.getLogger('flask.cache')

def gen_key_factory(key_pattern, arg_names, defaults):
    args = dict(list(zip(arg_names[-len(defaults):], defaults))) if defaults else {}
    if isinstance(key_pattern, collections.Callable):
        names = inspect.getargspec(key_pattern)[0]
    def gen_key(*a, **kw):
        aa = args.copy()
        aa.update(list(zip(arg_names, a)))
        aa.update(kw)
        if isinstance(key_pattern, collections.Callable):
            key = key_pattern(*[aa[n] for n in names])
        else:
            key = format_key_pattern(key_pattern, *[aa[n] for n in arg_names], **aa)
        return key and key.replace(' ','_'), aa
    return gen_key


def cache_obj(cache_key_reg, packer=encode, unpacker=decode):
    """A decorator that can cache function result.

    Example::

        @cache_obj({'key': 'item:{item_id}'})
        def get_item(item_id):
            return Item.query.get(item_id)

        @cache_obj({'key': 'item:{item_id}', 'expire': 60})
        def get_item(item_id):
            return Item.query.get(item_id)

        @cache_obj({'key': lambda filename: md5(filename).hexdigest()})
        def get_file(filename):
            return remote.fetch_file_data(filename)

    :param cache_key_reg: a dict-like object contains `key` and `expire`. `cache_obj` will inspect function arguments and format `cache_key_reg['key']` if `cache_key_reg['key']` is a string, or apply them to `cache_key_reg['key']` if `cache_key_reg['key']` is a callable object. `expire` is an integer. The unit is second.
    :param packer: a method used to encode function result.
    :param unpacker: a callable object used to decode msgpack data.
    """

    def deco(f, *a, **kw):
        key_pattern = cache_key_reg.get('key')
        expire = cache_key_reg.get('expire', None)
        arg_names, varargs, varkw, defaults = inspect.getargspec(f)
        if varargs or varkw:
            raise Exception("do not support varargs")
        gen_key = gen_key_factory(key_pattern, arg_names, defaults)

        key, args = gen_key(*a, **kw)
        if not key:
            return f(*a, **kw)
        if isinstance(key, text_type):
            key = key.encode("utf8")

        try:
            r = mc.get(key)
        except ConnectionError:
            return f(*a, **kw)

        r = unpacker(r) if r else None

        # set cache
        if r is None:
            r = f(*a, **kw)
            if r is not None:
                mc.set(key, packer(r), expire)
        else:
            logger.info('Cache read - %s',key)

        return r

    return make_deco(
        deco,
        cache_key_reg=cache_key_reg,
        packer=packer,
        unpacker=unpacker,
    )


def delete_obj(cache_key_reg):
    """Delete object cache

    :param cache_key_reg: a dict-like object contains 'key'.
    """

    def deco(f, *a, **kw):
        key_pattern = cache_key_reg.get('key')
        arg_names, varargs, varkw, defaults = inspect.getargspec(f)
        if varargs or varkw:
            raise Exception("do not support varargs")
        gen_key = gen_key_factory(key_pattern, arg_names, defaults)

        key, _ = gen_key(*a, **kw)
        if not key:
            return f(*a, **kw)
        if isinstance(key, text_type):
            key = key.encode("utf8")
        ret = f(*a, **kw)
        mc.delete(key)
        return ret

    return make_deco(
        deco,
        cache_key_reg=cache_key_reg,
    )


def delete_cache(cache_key_reg, **kw):
    """Delete cache via cache key registry.

    Example::

        delete_cache({'key': 'item:{item_id}'}, item_id=1)
    """
    key_pattern = cache_key_reg.get('key')
    key = format_key_pattern(key_pattern, **kw)
    key = key.replace(' ', '_')
    if isinstance(key, text_type):
        key = key.encode("utf8")
    mc.delete(key)
    logger.info('Cache delete - %s', key)

def cache_hash(cache_key_reg, packer=encode, unpacker=decode):
    """A decorator that can cache function result into redis hash.

    Example::

        @cache_hash({'key': '{item_id}', 'hash_key': 'item'})
        def get_item(item_id):
            return Item.query.get(item_id)

    :param cache_key_reg: a dict-like object contains `hash_key`, `key`. `hash_key` is a string as redis hash key. `key` is a template string or a callable object as hash field key.
    """

    def deco(f, *a, **kw):
        hash_key = cache_key_reg.get('hash_key')
        key = cache_key_reg.get('key')
        expire = cache_key_reg.get('expire', None)
        arg_names, varargs, varkw, defaults = inspect.getargspec(f)
        if varargs or varkw:
            raise Exception('do not support varargs')
        gen_key = gen_key_factory(key, arg_names, defaults)

        key, args = gen_key(*a, **kw)
        if not key:
            return f(*a, **kw)
        if isinstance(key, text_type):
            key = key.encode('utf8')

        try:
            r = mc.hget(hash_key, key)
        except ConnectionError:
            return f(*a, **kw)

        if r is not None:
            logger.info('HashCache read - %s - %s', hash_key, key)
            return unpacker(r) if r else None

        r = f(*a, **kw)
        if r is None:
            return r
        mc.hset(hash_key, key, packer(r))
        return r

    return make_deco(
        deco,
        cache_key_reg=cache_key_reg,
        packer=packer,
        unpacker=unpacker,
    )


def hash_del(cache_key_reg, **kw):
    """Delete hash field.

    Example::

        hash_del({'key': '{item_id}', 'hash_key': 'item'}, item_id=1)
    """
    hash_key = cache_key_reg.get('hash_key')
    key_pattern = cache_key_reg.get('key')
    key = format_key_pattern(key_pattern, **kw)
    mc.hdel(hash_key, key)


def cache_list(cache_key_reg, packer=str, unpacker=int):

    def deco(f, *a, **kw):
        key_pattern = cache_key_reg.get('key')
        expire = cache_key_reg.get('expire', None)
        arg_names, varargs, varkw, defaults = inspect.getargspec(f)
        if varargs or varkw:
            raise Exception("do not support varargs")
        gen_key = gen_key_factory(key_pattern, arg_names, defaults)

        key, args = gen_key(*a, **kw)
        if not key:
            return f(*a, **kw)
        if isinstance(key, text_type):
            key = key.encode("utf8")

        try:
            r = mc.smembers(key)
        except ConnectionError:
            return f(*a, **kw)

        r = [unpacker(rv) for rv in r]

        # set cache
        if not r:
            r = f(*a, **kw)
            if r:
                mc.delete(key)
                mc.sadd(key, *list(map(packer, r)))
        else:
            logger.info('Cache read - %s', key)

        return r

    return make_deco(
        deco,
        cache_key_reg=cache_key_reg,
        packer=packer,
        unpacker=unpacker,
    )



def list_add(cache_key_reg, value, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    mc.sadd(key, value)


def list_rem(cache_key_reg, value, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    mc.srem(key, value)


def list_len(cache_key_reg, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    return mc.scard(key)


def exists(cache_key_reg, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    return mc.exists(key)


def set_add(cache_key_reg, value, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    return mc.sadd(key, value)


def set_rem(cache_key_reg, value, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    return mc.srem(key, value)


def set_len(cache_key_reg, **kw):
    key_pattern = cache_key_reg.get('key')
    expire = cache_key_reg.get('expire', None)
    key = format_key_pattern(key_pattern, **kw)

    return mc.scard(key)


def cache_counter(cache_key_reg, packer=str, unpacker=int):
    """A decorator that can cache counter function result.

    Example::

        @cache_counter({'key': 'group_members:{group_id}', 'expire': 60})
        def get_group_members_count(group_id):
            return GroupMember.query.filter_by(group_id).count()

    :param cache_key_reg: a dict-like object contains `key` and `expire`.
    """

    def deco(f, *a, **kw):
        key_pattern = cache_key_reg.get('key')
        expire = cache_key_reg.get('expire', None)
        arg_names, varargs, varkw, defaults = inspect.getargspec(f)
        if varargs or varkw:
            raise Exception("do not support varargs")
        gen_key = gen_key_factory(key_pattern, arg_names, defaults)

        key, args = gen_key(*a, **kw)
        if not key:
            return f(*a, **kw)
        if isinstance(key, text_type):
            key = key.encode("utf8")

        try:
            r = mc.get(key)
        except ConnectionError:
            return f(*a, **kw)

        if r is None:
            r = f(*a, **kw)
            if r is not None:
                if not isinstance(r, integer_types):
                    raise Exception("Only support cache counters!")
                mc.set(key, packer(r), expire)
        else:
            logger.info('Counter cache read - %s', key)

        return unpacker(r)

    return make_deco(
        deco,
        cache_key_reg=cache_key_reg,
        packer=packer,
        unpacker=unpacker,
    )


def inc_counter(cache_key_reg, delta=1, **kw):
    """Increase counter value.

    :param cache_key_reg:  a dict-like object contains `key`.
    :param delta: increment delta. an integer. Default is 1.
    :param kw: A dict of named parameters used to format `cache_key_reg['key']`.
    """
    key_pattern = cache_key_reg.get('key')
    key = format_key_pattern(key_pattern, **kw)

    return int(mc.incr(key, delta) or 0)


def dec_counter(cache_key_reg, delta=1, **kw):
    """Decrease counter value.

    :param cache_key_reg: a dict-like object contains `key`.
    :param delta: decrement delta. an integer. Default is 1.
    :param kw: A dict of named parameters used to format `cache_key_reg['key']`.
    """
    key_pattern = cache_key_reg.get('key')
    key = format_key_pattern(key_pattern, **kw)

    return int(mc.decr(key, delta) or 0)


def get_counter(cache_key_reg, **kw):
    """Get counter value.

    :param cache_key_reg: a dict-like object contains `key`.
    :param kw: A dict of named parameters used to format `cache_key_reg['key']`.
    """
    key_pattern = cache_key_reg.get('key')
    key = format_key_pattern(key_pattern, **kw)

    return int(mc.get(key) or 0)

def set_counter(cache_key_reg, value=0, **kw):
    """Set counter value.

    :param cache_key_reg: a dict-like object contains `key`.
    :param value: reset counter value with given value.
    :param kw: A dict of named parameters used to format `cache_key_reg['key']`.
    """
    key_pattern = cache_key_reg.get('key')
    key = format_key_pattern(key_pattern, **kw)

    return mc.set(key, value)

def reset_counter(cache_key_reg, **kw):
    """Reset counter value, alias for set_counter(cache_key_reg, 0, **kw)"""
    return set_counter(cache_key_reg, 0, **kw)
