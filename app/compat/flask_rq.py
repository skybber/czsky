"""
    flask_rq
    ~~~~~~~~

    RQ (Redis Queue) integration for Flask applications.

    :copyright: (c) 2012 by Matt Wright.
    :license: MIT, see LICENSE for more details.

"""

import redis

from flask import current_app
from rq import Queue, Worker


default_config = {
    'RQ_DEFAULT_HOST': 'localhost',
    'RQ_DEFAULT_PORT': 6379,
    'RQ_DEFAULT_PASSWORD': None,
    'RQ_DEFAULT_DB': 0
}


def config_value(name, key):
    name = name.upper()
    config_key = 'RQ_%s_%s' % (name, key)
    if not config_key in current_app.config \
            and not 'RQ_%s_URL' % name in current_app.config:
        config_key = 'RQ_DEFAULT_%s' % key
    return current_app.config.get(config_key, None)


def get_connection(queue='default'):
    url = config_value(queue, 'URL')
    if url:
        return redis.from_url(url, db=config_value(queue, 'DB'))
    return redis.Redis(host=config_value(queue, 'HOST'),
                       port=config_value(queue, 'PORT'),
                       password=config_value(queue, 'PASSWORD'),
                       db=config_value(queue, 'DB'))


def get_queue(name='default', **kwargs):
    kwargs['connection'] = get_connection(name)
    return Queue(name, **kwargs)


def job(func_or_queue=None):
    if callable(func_or_queue):
        func = func_or_queue
        queue = 'default'
    else:
        func = None
        queue = func_or_queue

    def wrapper(fn):
        def delay(*args, **kwargs):
            q = get_queue(queue)
            return q.enqueue(fn, *args, **kwargs)

        fn.delay = delay
        return fn

    if func is not None:
        return wrapper(func)

    return wrapper


class RQ(object):
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        for key, value in default_config.items():
            app.config.setdefault(key, value)
