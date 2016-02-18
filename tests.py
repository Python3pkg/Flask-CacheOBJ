# -*- coding: utf-8 -*-

import pytest
import fakeredis

from flask import Flask
from flask.ext.cacheobj import FlaskCacheOBJ, Msgpackable

app = Flask(__name__)
cache = FlaskCacheOBJ()
cache.init_app(app)

@pytest.fixture
def app(request):
    app  = Flask(__name__)
    ctx = app.app_context()
    ctx.push()
    request.addfinalizer(ctx.pop)
    return app

@pytest.fixture
def cache(app, request):
    cache = FlaskCacheOBJ()
    app.config['CACHE_HOST'] = 'localhost'
    cache.init_app(app)
    cache.mc = fakeredis.FakeStrictRedis()
    request.addfinalizer(cache.mc.flushall)
    return cache

def test_mc_initialized(cache):
    assert cache.mc

class Obj(Msgpackable):

    def __init__(self, id):
        self.id = id

def test_cache_obj(cache):
    @cache.obj({'key': 'test_cache_obj:{id}', 'expire': 1})
    def get(id):
        return Obj(id)
    assert not cache.mc.get('test_cache_obj:1')
    assert get(1)
    assert cache.mc.get('test_cache_obj:1')
    assert get(1)

def test_cache_list(cache):
    @cache.list({'key': 'test_cache_list:{id}', 'expire': 1})
    def get(id):
        return range(id)
    assert not cache.mc.smembers('test_cache_list:1')
    assert get(1)
    assert cache.mc.exists('test_cache_list:1')
    assert get(1)

def test_cache_hash(cache):
    @cache.hash({'key': '{id}', 'hash_key': 'item', 'expire': 1})
    def get(id):
        return Obj(1)
    assert not cache.mc.hget('item', '1')
    assert get(1)
    assert cache.mc.hget('item', '1')
    assert get(1)

def test_cache_counter(cache):
    @cache.counter({'key': 'test_cache_counter:{id}', 'expire': 1})
    def get(id):
        return int(id)

    assert not cache.mc.get('test_cache_counter:1')
    assert get(1)
    assert int(cache.mc.get('test_cache_counter:1'))
    assert get(1)
