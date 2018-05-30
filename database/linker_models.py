from database import db
from sqlalchemy import func
from enum import Enum

class MessageTypes(Enum):
    NETWORK = 1  # send notification of current network
    ACCOUNTS = 2  # send notification of current network
    CALL = 3
    CALL_RESPONSE = 4
    LOGOUT = 666

class LinkedTokens(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_token = db.Column(db.String(255), index=True)
    wallet_token = db.Column(db.String(255), index=True)
    code = db.Column(db.String(255), index=True)
    code_expires = db.Column(db.DateTime(timezone=True))
    current_rpc = db.Column(db.String(255), index=True)
    current_accounts = db.Column(db.JSON())
    pending_call = db.Column(db.JSON())
    current_return_url = db.Column(db.String(255))
    linked = db.Column(db.Boolean())
    app_info = db.Column(db.JSON())
    created_at = db.Column(
        db.DateTime(
            timezone=True),
        server_default=func.now())

# very hacky message queue, probably want a real one to be scalable
class LinkedSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_token = db.Column(db.String(255))
    linked_id = db.Column(db.Integer, db.ForeignKey('linked_tokens.id'),
                                 nullable=False)
    created_at = db.Column(
        db.DateTime(
            timezone=True),
        server_default=func.now())

class LinkedMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('linked_session.id'),
                                 nullable=False)
    type = db.Column(db.Enum(MessageTypes))
    data = db.Column(db.JSON())
    sent = db.Column(db.Boolean())
    created_at = db.Column(
        db.DateTime(
            timezone=True),
        server_default=func.now())


class WalletMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_token = db.Column(db.String(255), index=True)
    current_accounts = db.Column(db.String(255))
    type = db.Column(db.Enum(MessageTypes))
    data = db.Column(db.JSON())
    created_at = db.Column(
        db.DateTime(
            timezone=True),
        server_default=func.now())

