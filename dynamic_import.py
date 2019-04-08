# -*- coding: utf-8 -*-
import os
import sys


def import_from_file(module_path, module_name=None):
    if module_name is not None:
        if module_name in sys.modules:
            return sys.modules[module_name]
    module_path = os.path.realpath(module_path)
    if os.path.isdir(module_path):
        import pkgutil
        import importlib
        module = None
        if module_name is not None:
            packages = pkgutil.walk_packages(path=[module_path])
            for importer, name, is_package in packages:
                if name == module_name:
                    # module = importlib.import_module(name)
                    loader = importer.find_loader(name)
                    module = loader[0].load_module()
                    break
                else:
                    print(name, is_package)
            else:
                print('notfound')
            return module
        else:
            sys.path.append(module_path)
            module_name = os.path.basename(module_path)
            module = importlib.import_module(module_name)
            return module
    if module_name is None:
        module_name = os.path.splitext(os.path.basename(module_path))[0]
    import importlib.util
    if hasattr(importlib.util, 'spec_from_file_location'):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    elif sys.version_info >= (3, 0):
        from importlib.machinery import SourceFileLoader
        module = SourceFileLoader(module_name, module_path).load_module()
        return module
    else:
        import imp
        module = imp.load_source(module_name, module_path) # *.py
        # module = imp.load_compiled(module_name, module_path) # *.pyc
        return module