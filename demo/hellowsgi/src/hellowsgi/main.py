from webob import Request, Response

def MainFactory(global_config, **local_conf):
    return MainApplication()

class MainApplication(object):
    """An endpoint"""
    
    def __call__(self, environ, start_response):
        request = Request(environ)
        response = Response("Powered by collective.hostout!")
        return response(environ, start_response)