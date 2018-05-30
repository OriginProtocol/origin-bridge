from marshmallow import Schema, fields, ValidationError
from logic.service_utils import ServiceError
from flask import make_response, request
import inspect
from http.cookies import SimpleCookie
from datetime import datetime


class StandardRequest(Schema):
    pass


class StandardResponse(Schema):
    errors = fields.List(fields.Str)


class SafeResponseObj(object):
    data = None
    errors = None

class CookiedResponseObj(SafeResponseObj):
    cookies = []

def safe_handler(call):
    def __call_handler(*args, **kargs):
        rsp = SafeResponseObj()
        # TODO:wrap a try catch around the handler_call for errors
        # catch errors and set it in the response...
        data = call(*args, **kargs)
        rsp.data  = data
        return rsp
    return __call_handler

# cookies_def should be {arg_name:(cookie_name, cookie_extra)} or {arg_name:cookie_name}
# ret_keys is a list of positional names for formation of a dictionar
def cookies_handler(call, cookies_def = {},  ret_keys = None):
    call_args = inspect.getargspec(call)[0]
    def __call_handler(*args, **kargs):
        rsp = SafeResponseObj()
        ret_cookies = []
        for arg_name in call_args:
            if arg_name in cookies_def:
                cookie_info = cookies_def[arg_name]
                if isinstance(cookie_info, str):
                    cookie_name = cookie_info
                    cookies_extra = {}
                else:
                    (cookie_name, _) = cookie_info
                kargs[arg_name] = request.cookies.get(cookie_name)
        ret = call(*args, **kargs)
        if isinstance(ret_keys, (list, tuple)):
            ret = dict(zip(ret_keys, ret))
        elif isinstance(ret_keys, str):
            ret = {ret_keys:ret}
        cookies_out = SimpleCookie()
        for arg_name, cookie_info in cookies_def.items():
            if arg_name in ret:
                if isinstance(cookie_info, str):
                    cookie_name = cookie_info
                    cookies_extra = {}
                else:
                    (cookie_name, cookies_extra) = cookie_info
                value = ret.pop(arg_name)
                if not value is None:
                    cookies_out[cookie_name] = value
                    cookies_out[cookie_name].update(cookies_extra)
        rsp.data = ret
        rsp.cookies = cookies_out
        return rsp
    return __call_handler


def handle_request(data, handler, request_schema, response_schema):
    try:
        req = request_schema().load(data)
    # Handle validation errors
    except ValidationError as validation_err:
        errors = []
        for attr, msg in validation_err.messages.items():
            errors.append("%s: %s" % (attr, " ".join(msg).lower()))
        resp = {
            'errors': errors
        }
        return response_schema().dump(resp), 422
    try:
        resp = handler(**req)
        resp_data = response_schema().dump(resp.data)
        if getattr(resp, "cookies", None):
            return resp_data, 200, {"Set-Cookie":resp.cookies.output(header="").strip(),
                    "Last-Modified": datetime.now(),
                    "Cache-Control": 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0',
                    'Pragma': "no-cache",
                    'Expires': '-1'}
        else:
            return resp_data, 200
    # Handle custom errors we have explicitly thrown from our services
    except ServiceError as service_err:
        resp = {
            'errors': [str(service_err)]
        }
        return response_schema().dump(resp), 422
