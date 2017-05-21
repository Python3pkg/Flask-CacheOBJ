# -*- coding: utf-8 -*-

import redis

class RedisClient(object):

    def __init__(self, host='localhost', port=6379, password=None,
                 db=0, default_timeout=None, key_prefix=None):
        self.default_timeout = default_timeout
        self._client = redis.Redis(host=host, port=port, password=password, db=db)

        if key_prefix:
            def _make_key(key):
                return key_prefix + key
            self._make_key = _make_key
        else:
            self._make_key = lambda x: x

    def get(self, key):
        return self._client.get(self._make_key(key))

    def set(self, key, value, timeout=None):
        if timeout is None:
            timeout = self.default_timeout

        if timeout is not None:
            self._client.setex(self._make_key(key), value, timeout)
        else:
            self._client.set(self._make_key(key), value)

    def hget(self, key, k):
        return self._client.hget(self._make_key(key), k)

    def hset(self, key, k, v):
        return self._client.hset(self._make_key(key), k, v)

    def hdel(self, key, *ks):
        return self._client.hdel(self._make_key(key), *ks)

    def hgetall(self, key):
        return self._client.hgetall(self._make_key(key))

    def delete(self, *keys):
        self._client.delete(*[self._make_key(key) for key in keys])

    def incr(self, key, delta=1):
        return self._client.incr(self._make_key(key), delta)

    inc = incr

    def decr(self, key, delta=1):
        return self._client.decr(self._make_key(key), delta)

    dec = decr

    def bulk_delete(self, pattern):
        keys = self._client.keys(self._make_key(pattern))
        if keys:
            self._client.delete(*keys)

    def sadd(self, key, *values):
        return self._client.sadd(self._make_key(key), *values)

    def srem(self, key, *values):
        return self._client.srem(self._make_key(key), *values)

    def smembers(self, key):
        return self._client.smembers(self._make_key(key))

    def sismember(self, key, member):
        return self._client.sismember(self._make_key(key), member)

    def scard(self, key):
        return self._client.scard(self._make_key(key))

    def exists(self, key):
        return self._client.exists(self._make_key(key))

    def lpush(self, key, *values):
        return self._client.lpush(self._make_key(key), *values)

    def llen(self, key):
        return self._client.llen(self._make_key(key))

    def rpop(self, key):
        return self._client.rpop(self._make_key(key))

    def lrange(self, key, start, end):
        return self._client.lrange(self._make_key(key), start, key)

    def expire(self, key, time):
        return self._client.expire(self._make_key(key), time)

    def mget(self, keys):
        return self._client.mget([self._make_key(key) for key in keys])

    def mset(self, **kw):
        return self._client.mset({
            self._make_key(key): value for key, value in kw.items()
        })


    def _flushall(self):
        return self._client.flushall()
