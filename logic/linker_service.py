from database import db
from database.db_models import LinkedTokens, LinkedMessage, MessageTypes, WalletMessage, LinkedSession
from sqlalchemy import JSON
from sqlalchemy import cast
from .notifier_service import Notification, EthNotificationEndpoint, send_single_notification 
from util.contract import ContractHelper
from util.ipfs import IPFSHelper
from util.time_ import utcnow
import datetime
from config import settings
from enum import Enum
from web3 import Web3
import logging
import uuid
import random, string


CODE_EXPIRATION_TIME_MINUTES = 60

def _generate_code():
    for i in range(10):
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        #let's make sure this is code isn't used already
        if not LinkedTokens.query.filter_by(code = code).filter(LinkedTokens.code_expires > utcnow()).count():
            return code
    raise Exception("We hit max retries without finding a none repreated code!")

def generate_code(client_token, session_token, return_url, pending_call=None, force_relink=False):
    if not client_token:
        #create a new uuid
        client_token = str(uuid.uuid1())
        linked_obj = LinkedTokens(client_token=client_token,
                                linked = False)
    else:
        # todo check verification sig if we want this to be a verified endpoint
        linked_obj = LinkedTokens.query.filter_by(
            client_token = client_token).first()
    if force_relink:
        linked_obj.linked = False
        linked_obj.wallet_token = None
    if not linked_obj.linked:
        linked_obj.code = _generate_code()
        linked_obj.code_expires = utcnow() + datetime.timedelta(minutes=CODE_EXPIRATION_TIME_MINUTES)
        linked_obj.current_return_url = return_url
    db.session.add(linked_obj)
    db.session.commit()
    #if the session_token's not there, or there's no session token in the db
    if not (session_token and LinkedSession.query.filter_by(session_token = session_token, linked_id = linked_obj.id).first()):
        session_token = generate_init_session(linked_obj)

    if pending_call and not linked_obj.linked:
        pending_call["session_token"] = session_token
        linked_obj.pending_call = pending_call
        db.session.add(linked_obj)
        db.session.commit()

    if not linked_obj.linked:
        return client_token, session_token, linked_obj.code, False
    else:
        return client_token, session_token, "", True

def get_linked_messages(db_linked_session, last_message_id, purge = False):
    linked_messages_query = LinkedMessage.query.filter_by(session_id = db_linked_session.id)
    if last_message_id is not None:
        if purge:
            linked_messages_query.filter(LinkedMessage.id <= last_message_id).delete(synchronize_session = False)
            db.session.commit()
        linked_messages_query = linked_messages_query.filter(LinkedMessage.id > last_message_id)

    messages = []
    for db_message in linked_messages_query:
        message_type = db_message.type
        message = {'type':message_type.name, 'id':db_message.id}
        if message_type == MessageTypes.NETWORK:
            message['network_rpc'] = db_message.data
        elif message_type == MessageTypes.ACCOUNTS:
            message['accounts'] = db_message.data
        else:
            message['result'] = db_message.data['result']
            message['call_id'] = db_message.data['call_id']
        messages.append(message)
    print("we got messages:", messages)
    return messages

def send_init_messages(db_linked_session, linked_obj):
    network_msg = LinkedMessage(session_id=db_linked_session.id, type = MessageTypes.NETWORK, data = linked_obj.current_rpc)
    accounts_msg = LinkedMessage(session_id=db_linked_session.id, type = MessageTypes.ACCOUNTS, data = linked_obj.current_accounts)

    db.session.add(network_msg)
    db.session.add(accounts_msg)

def generate_init_session(linked_obj):
    #create a new session
    session_token = str(uuid.uuid1())
    db_linked_session = LinkedSession(session_token = session_token, linked_id = linked_obj.id)
    db.session.add(db_linked_session)
    db.session.commit()

    #send over the current accounts
    if linked_obj.linked:
        send_init_messages(db_linked_session, linked_obj)
    db.session.commit()
    return session_token
    
def link_messages(client_token, session_token, last_message_id=None):
    if not client_token:
        return client_token, None, [], False
    linked_obj = LinkedTokens.query.filter_by(
        client_token = client_token).first()
    if not linked_obj:
        #reset the client token
        return "", None, [], False
    if not linked_obj.linked:
        return client_token, session_token, [], False

    generated = False
    if not session_token:
        generated = True
        session_token = generate_init_session(linked_obj)
        
    db_linked_session = LinkedSession.query.filter_by(session_token = session_token, linked_id = linked_obj.id).first()
    if not db_linked_session:
        if generated:
            raise Exception("Problem generating the session.")
        #if it's a bad session... generate this again.
        session_token = generate_init_session(linked_obj)
        db_linked_session = LinkedSession.query.filter_by(session_token = session_token, linked_id = linked_obj.id).first()

    return client_token, session_token, get_linked_messages(db_linked_session, last_message_id, purge = True), True

def wallet_messages(wallet_token, accounts, last_message_id=None):
    if not wallet_token:
        return []

    #contains is hack for now, it should be equals
    wallet_messages_query = WalletMessage.query.filter_by(wallet_token = wallet_token).filter(WalletMessage.current_accounts.contains(accounts[0]))
    if last_message_id is not None:
        wallet_messages_query.filter(WalletMessage.id <= last_message_id).delete(synchronize_session = False)
        db.session.commit()
        wallet_messages_query = wallet_messages_query.filter(WalletMessage.id > last_message_id)

    messages = []
    for db_message in wallet_messages_query:
        message_type = db_message.type
        message = {'type':message_type.name, 'id':db_message.id}
        if message_type == MessageTypes.CALL:
            message['call'] = db_message.data['call']
            message['call_id'] = db_message.data['call_id']
            if "session_token" in db_message.data:
                message['session_token'] = db_message.data['session_token']
            if db_message.data.get("return_url"):
                message["return_url"] = db_message.data["return_url"]
        messages.append(message)
    return messages

def link_wallet(wallet_token, code, current_rpc, current_accounts):
    # TODO make sure there's only one of these
    unlinked = LinkedTokens.query.filter_by(code = code).filter(LinkedTokens.code_expires > utcnow()).first()
    if not unlinked:
        return "", False, None

    #grab the last pending call
    last_pending_call = unlinked.pending_call

    unlinked.wallet_token = wallet_token
    unlinked.code = None
    unlinked.linked = True
    unlinked.current_rpc = current_rpc
    unlinked.current_accounts = current_accounts
    unlinked.pending_call = None

    db.session.add(unlinked)

    #anyone that's listening before, let's send them some good stuff
    if unlinked.id:
        for linked_session in LinkedSession.query.filter_by(linked_id = unlinked.id):
            send_init_messages(linked_session, unlinked)

    db.session.commit()
    return unlinked.current_return_url, True, last_pending_call

def call_wallet(client_token, session_token, accounts, call_id, call, return_url = None):
    if not client_token:
        return False
    linked_obj = LinkedTokens.query.filter_by(
        client_token = client_token, linked= True).first()
    if not linked_obj:
        return False
    session_obj = LinkedSession.query.filter_by(linked_id = linked_obj.id, session_token = session_token).first()

    call_data = {"call_id":call_id,
                "call":call,
                "session_token":session_obj.session_token}

    if return_url:
        call_data["return_url"] = return_url

    call_msg = WalletMessage(wallet_token = linked_obj.wallet_token, current_accounts = accounts, type = MessageTypes.CALL, data = call_data)
    db.session.add(call_msg)
    db.session.commit()
    # tell the phone there's a transaction pending
    # TODO: sending this only to verified addresses
    eth_address = Web3.toChecksumAddress(accounts[0])
    endpoint = EthNotificationEndpoint.query.filter_by(eth_address=eth_address, device_token=linked_obj.wallet_token, active=True).first()
    send_single_notification(endpoint, Notification.TRANSACTION_PENDING, {})
    return True

def wallet_called(wallet_token, call_id, session_token, result):
    session_obj = LinkedSession.query.filter_by(session_token = session_token).first()
    if not session_obj:
        raise Exception("Session does not exist")
    linked_obj = LinkedTokens.query.get(session_obj.linked_id)
    if not linked_obj:
        raise Exception("Session not linked")
    if not linked_obj.wallet_token == wallet_token:
        raise Exception("Wallet linked to a different session")

    response_data = {"call_id":call_id,
            "result": result}
    response_msg = LinkedMessage(session_id=session_obj.id, type = MessageTypes.CALL_RESPONSE, data = response_data )
    db.session.add(response_msg)
    db.session.commit()
    return True




