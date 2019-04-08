"""
dynamic python files
"""
import os
import logging
import signal
import time
from datetime import datetime
import functools
import types

import tornado.web
import tornado.ioloop
import tornado.gen
import tornado.options
import tornado.httpserver
from concurrent.futures import ProcessPoolExecutor

from dynamic_import import import_from_file


tornado.options.define("port", default=8787, help="listen on the given port", type=int)

MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 1

def sig_handler(server, sig, frame):
    # from: https://gist.github.com/wonderbeyond/d38cd85243befe863cdde54b84505784
    io_loop = tornado.ioloop.IOLoop.current()

    def stop_loop(deadline):
        now = time.time()
        if not io_loop.closing:
            if now < deadline:
                logging.info('Waiting for next tick')
                io_loop.add_timeout(now + 1, stop_loop, deadline)
            else:
                io_loop.stop()
                logging.info('Shutdown finally')

    def shutdown():
        logging.info('Stopping http server')
        server.stop()
        logging.info('Will shutdown in %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
        stop_loop(time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)

    logging.warning('Caught signal: %s', sig)
    io_loop.add_callback_from_signal(shutdown)

def dynamic_response(file_path, path_args, path_kwargs, request):
    module = import_from_file(file_path)
    if isinstance(module, types.ModuleType):
        if hasattr(module, 'response'):
            response_func = module.response
            if hasattr(response_func, '__call__'):
                response_result = response_func(path_args, path_kwargs, request)
                if response_result is None:
                    return tornado.web.HTTPError(500, 'response()方法未返回数据')
                else:
                    return response_result
        return tornado.web.HTTPError(500, 'response()方法未正确实现')
    else:
        return tornado.web.HTTPError(500, '模块有误')

def pickleable_request(request):
    # https://www.tornadoweb.org/en/stable/httputil.html#tornado.httputil.HTTPServerRequest
    return {
        'method': request.method,
        'uri': request.uri,
        'path': request.path,
        'query': request.query,
        'version': request.version,
        'version': request.version,
        'headers': request.headers,
        'body': request.body,
        'remote_ip': request.remote_ip,
        'protocol': request.protocol,
        'host': request.host,
        'arguments': request.arguments,
        'query_arguments': request.query_arguments,
        'body_arguments': request.body_arguments,
        'files': request.files,
        'connection': None,
        'cookies': request.cookies,
        'full_url': request.full_url(),
        'request_time': request.request_time(),
        'get_ssl_certificate': None
    }

class MainHandler(tornado.web.RequestHandler):
    def initialize(self, root):
        self.root = root

    @tornado.gen.coroutine
    def prepare(self):
        # https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler
        print(self.path_args, type(self.path_args))
        print(self.path_kwargs, type(self.path_kwargs))
        url_path = self.path_kwargs.get('file_path')
        if os.path.sep != "/":
            url_path = url_path.replace("/", os.path.sep)
        absolute_path = os.path.abspath(os.path.join(self.root, url_path))
        root = os.path.abspath(self.root)
        if not root.endswith(os.path.sep):
            root += os.path.sep
        if not (absolute_path + os.path.sep).startswith(root):
            raise tornado.web.HTTPError(403, "%s is not in root directory", url_path)
        if not os.path.exists(absolute_path):
            raise tornado.web.HTTPError(404)
        if not os.path.isfile(absolute_path):
            raise tornado.web.HTTPError(403, "%s is not a file", url_path)
        executor = ProcessPoolExecutor(1)
        # 动态调用
        result = yield executor.submit(
            dynamic_response,
            absolute_path,
            self.path_args,
            self.path_kwargs,
            pickleable_request(self.request)
        )
        # 响应结果
        self.write(str(result))
        self.finish()
        executor.shutdown()

def do_heartbeat():
    logging.debug('heartbeat-> ' + str(datetime.now()))
    pass

if __name__ == '__main__':
    # 设置日志模式为Debug，默认为Info
    tornado.options.options.logging = 'debug'
    # 解析配置
    tornado.options.parse_command_line()
    # 静态文件目录
    static_path_dir = os.getcwd()
    favicon_path_dir = os.getcwd()
    # 视图函数列表
    handlers = [
        (r'/(favicon\.ico)', tornado.web.StaticFileHandler, {'path': favicon_path_dir}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': static_path_dir}),
        tornado.web.URLSpec(r"/(?P<file_path>[^/]+)", MainHandler, {'root': os.getcwd()}),
    ]
    # 实例化应用
    application = tornado.web.Application(handlers)
    # 实例化HTTP服务
    server = tornado.httpserver.HTTPServer(
        application,
        no_keep_alive=False,
        xheaders=True,
        idle_connection_timeout=0.29
    )
    listen_port = tornado.options.options.port
    server.bind(listen_port)
    server.start(1)
    signal.signal(signal.SIGTERM, functools.partial(sig_handler, server))
    signal.signal(signal.SIGINT, functools.partial(sig_handler, server))
    logging.info('http://127.0.0.1:{0}/'.format(listen_port))
    logging.warning('demo: http://127.0.0.1:8787/demo.py')
    # 心跳检测
    tornado.ioloop.PeriodicCallback(
        callback=do_heartbeat,
        callback_time=1000 # 1000毫秒(1秒)
    ).start()
    # tornado.ioloop.IOLoop.instance().start()
    tornado.ioloop.IOLoop.current().start()
    logging.info("Exit...")
