# -*- coding: utf-8 -*-


import inspect
import msgpack
import datetime
import dateutil.parser
import pytz
import time

__all__ = [
    'Msgpackable', 'MsgpackMisconfiguredError',
    'msgpackify',
    'encode', 'decode',
]

_msgpackable_registry = {} # pylint: disable=C0103

MSGPACK_TYPE_KEY = '_t'
MSGPACK_VALUE_KEY = 'v'

MSGPACK_TYPE_DATE = 'd'
MSGPACK_TYPE_DATETIME = 'dt'
MSGPACK_TYPE_DATETIME_ISO8601 = 'di'


class MsgpackMisconfiguredError(Exception):
    pass


class MsgpackableMeta(type):

    def __new__(typ, name, bases, dct):
        cls = super(MsgpackableMeta, typ).__new__(typ, name, bases, dct)
        MsgpackableMeta._register_msgpackable(cls)
        return cls

    @staticmethod
    def _register_msgpackable(cls):
        if getattr(cls, '_msgpack_abstract_class', False):
            delattr(cls, '_msgpack_abstract_class')
            return cls
        if not getattr(cls, '_msgpack_key', None):
            cls._msgpack_key = '%s.%s' % (cls.__module__, cls.__name__)
        if cls._msgpack_key in _msgpackable_registry:
            raise TypeError('_msgpack_key "%s" has conflicts: %s, %s' % (
                cls._msgpack_key,
                _msgpackable_registry[cls._msgpack_key],
                cls
            ))
        _msgpackable_registry[cls._msgpack_key] = cls


class _Msgpackable(object):
    _msgpack_key = None

    def _msgpack_pack_me(self, fields=None):
        if not fields:
            argspec = inspect.getargspec(self.__init__)
            fields = argspec.args[1:]
        return {k: self.__dict__[k] for k in fields}

    @classmethod
    def _msgpack_unpack_me(cls, kw):
        return cls(**kw)


class Msgpackable(_Msgpackable, metaclass=MsgpackableMeta):
    _msgpack_abstract_class = True


def msgpackify(cls,
               _mp_is_abstract=True,
               _mp_additional_mixins=None,
               **attrs):
    metatype = type(cls)

    if metatype is type:
        metatype = MsgpackableMeta
    else:
        old_metatype = metatype

        def new(typ, name, bases, dct):
            cls = super(old_metatype, typ).__new__(typ, name, bases, dct)
            MsgpackableMeta._register_msgpackable(cls)
            return cls

        metatype = type(
            '%sMsgpackableMeta' % metatype.__name__,
            (old_metatype, ),
            {'__new__': new}
        )

    new_cls = metatype(
        '%sMsgpackable' % cls.__name__,
        (cls, _Msgpackable) + (_mp_additional_mixins or ()),
        dict(_msgpack_abstract_class=_mp_is_abstract, **attrs)
    )

    return new_cls

def get_registerd_msgpackables():
    return list(_msgpackable_registry.items())

def _unregister_class(cls):
    if cls._msgpack_key in _msgpackable_registry:
        del _msgpackable_registry[cls._msgpack_key]


def msgpack_encode(obj, fields=None):
    if isinstance(obj, _Msgpackable):
        return {
            MSGPACK_TYPE_KEY: obj._msgpack_key,
            MSGPACK_VALUE_KEY: obj._msgpack_pack_me(fields)
        }

    if isinstance(obj, datetime.datetime):
        if not obj.tzinfo or obj.tzinfo == pytz.UTC:
            return {
                MSGPACK_TYPE_KEY: MSGPACK_TYPE_DATETIME,
                MSGPACK_VALUE_KEY: (
                    time.mktime(obj.utctimetuple()) +
                    obj.microsecond / 1e6
                )
            }

        return {
            MSGPACK_TYPE_KEY: MSGPACK_TYPE_DATETIME_ISO8601,
            MSGPACK_VALUE_KEY: obj.isoformat()
        }

    if isinstance(obj, datetime.date):
        return {
            MSGPACK_TYPE_KEY: MSGPACK_TYPE_DATE,
            MSGPACK_VALUE_KEY: obj.toordinal()
        }

    return obj


def msgpack_decode(obj):
    if isinstance(obj, dict) and MSGPACK_TYPE_KEY in obj:
        type_key = obj[MSGPACK_TYPE_KEY]
        value = obj[MSGPACK_VALUE_KEY]
        if type_key == MSGPACK_TYPE_DATETIME:
            return datetime.datetime.fromtimestamp(value)
        if type_key == MSGPACK_TYPE_DATETIME_ISO8601:
            return dateutil.parser.parse(value)
        if type_key == MSGPACK_TYPE_DATE:
            return datetime.date.fromordinal(value)
        if type_key not in _msgpackable_registry:
            raise MsgpackMisconfiguredError('missing type: %s' % type_key)
        classtype = _msgpackable_registry[type_key]
        return classtype._msgpack_unpack_me(value)

    return obj


def msgpack_decode_silent(obj):
    try:
        return msgpack_decode(obj)
    except MsgpackMisconfiguredError:
        return None


def encode(obj, fields=None):
    """Encode python object to msgpack binary data.
    """
    return msgpack.packb(msgpack_encode(obj, fields))


def decode(obj, silent=False):
    """Decode msgpack binary data to python object.
    """
    if obj is None:
        return
    if silent:
        return msgpack.unpackb(obj, object_hook=msgpack_decode_silent, encoding='utf8')
    return msgpack.unpackb(obj, object_hook=msgpack_decode, encoding='utf8')
