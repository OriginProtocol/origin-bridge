from flask import request
from flask_restful import Resource
from marshmallow import fields
from marshmallow_enum import EnumField
import inspect

from logic import linker_service
from api.helpers import StandardResponse, StandardRequest, cookies_handler, handle_request


cookies_def = {"client_token":("ct", {"expires":15 * 24 * 3600})}


class GenerateCodeRequest(StandardRequest):
    return_url = fields.Str()
    session_token = fields.Str()
    pending_call = fields.Field()

class GenerateCodeResponse(StandardResponse):
    session_token = fields.Str()
    link_code = fields.Str()
    linked = fields.Boolean()

class GenerateCode(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.generate_code, cookies_def, ("client_token", "session_token", "link_code", "linked")),
            request_schema=GenerateCodeRequest,
            response_schema=GenerateCodeResponse)

class LinkMessagesRequest(StandardRequest):
    session_token = fields.Str(required=True)
    last_message_id = fields.Integer()

class LinkMessagesResponse(StandardResponse):
    session_token = fields.Str()
    messages = fields.List(fields.Dict())
    linked = fields.Boolean()

class LinkMessages(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.link_messages, cookies_def, ("client_token", "session_token", "messages", "linked")),
            request_schema=LinkMessagesRequest,
            response_schema=LinkMessagesResponse)

class WalletMessagesRequest(StandardRequest):
    wallet_token = fields.Str(required=True)
    last_message_id = fields.Integer()
    accounts = fields.List(fields.Str())

class WalletMessagesResponse(StandardResponse):
    messages = fields.List(fields.Dict())

class WalletMessages(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.wallet_messages, ret_keys = "messages"),
            request_schema=WalletMessagesRequest,
            response_schema=WalletMessagesResponse)

class CallWalletRequest(StandardRequest):
    session_token = fields.Str(require=True)
    call_id = fields.Str(required=True)
    accounts = fields.List(fields.Str())
    call = fields.List(fields.Field(), required=True)
    return_url = fields.Str()

class CallWalletResponse(StandardResponse):
    success = fields.Boolean()

class CallWallet(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.call_wallet, cookies_def, "success"),
            request_schema=CallWalletRequest,
            response_schema=CallWalletResponse)

class WalletCalledRequest(StandardRequest):
    wallet_token = fields.Str(required=True)
    call_id = fields.Str(required=True)
    session_token = fields.Str(required=True)
    result = fields.Field(required=True)

class WalletCalledResponse(StandardResponse):
    success = fields.Boolean()

class WalletCalled(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.wallet_called, ret_keys="success"),
            request_schema=WalletCalledRequest,
            response_schema=WalletCalledResponse)

class LinkInfoRequest(StandardRequest):
    code = fields.Str(required=True)

class LinkInfoResponse(StandardResponse):
    return_url = fields.Str()
    app_info = fields.Field()
    link_id = fields.Str()

# TODO: this needs to be a GET
class LinkInfo(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.link_info, cookies_def, ("return_url", "app_info", "link_id", "expires_at")),
            request_schema=LinkInfoRequest,
            response_schema=LinkInfoResponse)

class LinkWalletRequest(StandardRequest):
    wallet_token = fields.Str(required=True)
    code = fields.Str(required=True)
    current_rpc = fields.Str(required=True)
    current_accounts = fields.List(fields.Str(), required=True)

class LinkWalletResponse(StandardResponse):
    return_url = fields.Str()
    linked = fields.Boolean()
    pending_call = fields.Field()
    app_info = fields.Field()
    link_id = fields.Str()
    linked_at = fields.Integer()

class LinkWallet(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.link_wallet, cookies_def, ("return_url","linked", "pending_call", "app_info", "link_id", "linked_at")),
            request_schema=LinkWalletRequest,
            response_schema=LinkWalletResponse)

class UnlinkRequest(StandardRequest):
    pass

class UnlinkResponse(StandardResponse):
    success = fields.Boolean()

class Unlink(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.unlink, cookies_def, "success"),
            request_schema=UnlinkRequest,
            response_schema=UnlinkResponse)

class UnlinkWalletRequest(StandardRequest):
    wallet_token = fields.Str(required=True)
    link_id = fields.Str(required=True)

class UnlinkWalletResponse(StandardResponse):
    success = fields.Boolean()

class UnlinkWallet(Resource):
    def post(self):
        return handle_request(
            data=request.json,
            handler=cookies_handler(linker_service.unlink_wallet, cookies_def, "success"),
            request_schema=UnlinkWalletRequest,
            response_schema=UnlinkWalletResponse)

class WalletLinks(Resource):
    def get(self, wallet_token):
        if wallet_token:
            return linker_service.get_links(wallet_token), 200

resources = {
    # 'hello-world-path': HelloWorldResource
    'generate-code': GenerateCode,
    'link-messages':LinkMessages,
    'link-info':LinkInfo,
    'wallet-messages':WalletMessages,
    'call-wallet':CallWallet,
    'wallet-called':WalletCalled,
    'link-wallet':LinkWallet,
    'wallet-links/<wallet_token>':WalletLinks,
    "unlink":Unlink,
    'unlink-wallet':UnlinkWallet
}
