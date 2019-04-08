def response(path_args, path_kwargs, request):
    from pprint import pprint
    pprint(path_args)
    pprint(path_kwargs)
    pprint(request)
    pass
    return 'hello'