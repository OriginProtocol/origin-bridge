from database import db
from database.db_models import EthNotificationEndpoint, EthNotificationTypes, Listing
from util.contract import ContractHelper
from util.ipfs import IPFSHelper
from config import settings
from enum import Enum
from web3 import Web3
import logging

# for apns2
from apns2.client import APNsClient
from apns2.payload import Payload
# for FCM
from pyfcm import FCMNotification

apns_client = None
fcm_client = None

PurchaseStages = ContractHelper.get_contract_enums("Purchase", "Stages")


class Notification(Enum):
    LIST = 1
    SOLD = 2
    PURCHASED = 3
    UPDATED = 4
    PENDING_PAYMENT = 5
    PENDING_PAY = 6
    PENDING_BUYER_CONFIRMATION = 7
    PENDING_BUY_CONFIRM = 8
    PENDING_SELLER_CONFIRM = 9
    PENDING_SELLER_CONFIRMATION = 10
    SELLER_DISPUTE = 11
    BUYER_DISPUTE = 12
    SELLER_REVIEW = 13
    BUYER_REVIEW = 14
    TRANSACTION_PENDING = 15
    INFO_TRANSACTION_PENDING = 16
    NEW_MESSAGE = 17


notification_messages = {
    Notification.LIST: "New listing online:{name}",
    Notification.SOLD: "You just sold {name}",
    Notification.PURCHASED: "You just purchased {name}",
    Notification.UPDATED: "Your listing, {name} has been updated",
    Notification.PENDING_PAYMENT: "Waiting for buyer payment",
    Notification.PENDING_PAY: "Payment required",
    Notification.PENDING_BUYER_CONFIRMATION: "Waiting for buyer confirmation",
    Notification.PENDING_BUY_CONFIRM: "Please confirm purchase",
    Notification.PENDING_SELLER_CONFIRM: "Please confirm sale",
    Notification.PENDING_SELLER_CONFIRMATION: "Waiting on seller confirmation",
    Notification.SELLER_DISPUTE: "Your item is in dispute",
    Notification.BUYER_DISPUTE: "Your purchase is in dispute",
    Notification.SELLER_REVIEW: "Your item is in review",
    Notification.BUYER_REVIEW: "Your purchase is in review",
    Notification.TRANSACTION_PENDING: "There is a transaction pending",
    Notification.INFO_TRANSACTION_PENDING: {"title": "{action} {name} pending",
        "body": "Please approve your {action} of {name}"},
    Notification.NEW_MESSAGE:"You've received a new message"
}

require_verified_messages = ()  # list of types in here


def register_eth_notification(
        eth_address, type, device_token, verification_signature=None):
    # todo check verification sig if we want this to be a verified endpoint
    eth_address = Web3.toChecksumAddress(eth_address)
    notification_obj = EthNotificationEndpoint.query.filter_by(
        eth_address=eth_address, device_token=device_token, type=type).first()
    if notification_obj:
        notification_obj.active = True
    else:
        notification_obj = EthNotificationEndpoint(eth_address=eth_address,
                                                   device_token=device_token,
                                                   type=type,
                                                   active=True)
    db.session.add(notification_obj)
    db.session.commit()
    logging.debug("token registered %s to %s" % (device_token, eth_address))

def new_eth_message(receivers):
    for receiver in receivers:
        eth_address = Web3.toChecksumAddress(receiver)
        send_notification(eth_address, Notification.NEW_MESSAGE)

def send_apn_notification(message, endpoint):
    token = endpoint.device_token
    payload = Payload(alert=message, sound="default", badge=1)
    if settings.APNS_CERT_FILE:
        # allows for reuse of apns client and reuse of connections
        # TODO: handles errors by fcm client
        global apns_client
        if not apns_client:
            apns_client = APNsClient(
                settings.APNS_CERT_FILE,
                password=settings.APNS_CERT_PASSWORD,
                use_sandbox=settings.DEBUG,
                use_alternative_port=False)
        topic = settings.APNS_APP_BUNDLE_ID
        apns_client.send_notification(token, payload, topic)
        logging.debug("%s sent to %s @ %s" %
                      (message, endpoint.eth_address, token))


def send_fcm_notification(message, endpoint):
    token = endpoint.device_token
    if settings.FCM_API_KEY:
        global fcm_client
        if not fcm_client:
            fcm_client = FCMNotification(api_key=settings.FCM_API_KEY)
        fcm_client.notify_single_device(
            registration_id=token,
            message_title=settings.FCM_TITLE,
            message_body=message)

def send_single_notification(notification_endpoint, notification_type, data):
    message = notification_messages[notification_type]

    if isinstance(message, dict):
        message = dict(message) # make copy
        for k in message:
            message[k] = message[k].format(**data)
        notify_message = message
    else:
        notify_message = message.format(**data)

    if notification_endpoint.type == EthNotificationTypes.APN:
        # send apn notification here
        send_apn_notification(notify_message, notification_endpoint)
    elif notification_endpoint.type == EthNotificationTypes.FCM:
        # send FCM notification here
        send_fcm_notification(notify_message, notification_endpoint)

def send_event_notification(*args, **kargs):
    if settings.ENABLE_EVENT_NOTIFICATIONS:
        send_notification(*args, **kargs)

def send_notification(notify_address, notification_type, **data):
    for notification_endpoint in EthNotificationEndpoint.query.filter_by(
            eth_address=notify_address, active=True):
        send_single_notification(notification_endpoint, notification_type, data)
        
def get_listing_picture(listing_obj, index=0):
    data = IPFSHelper().file_from_hash(listing_obj.ipfs_hash, root_attr='data')
    if data:
        pictures = data.get('pictures')
        if isinstance(pictures, list) and len(pictures) > index:
            return pictures[index]


def listing_info(listing_obj):
    return dict(name=listing_obj.ipfs_data.get('name'),
                description=listing_obj.ipfs_data.get('description'),
                pictures=get_listing_picture(listing_obj))


class Notifier():
    """
    Notifier sends mobile notifications.
    """
    @classmethod
    def notify_purchased(cls, purchase_obj):
        if not purchase_obj.listing_address:
            return

        seller_notification, buyer_notification = {
            PurchaseStages.COMPLETE: (
                Notification.SOLD,
                Notification.PURCHASED),

            PurchaseStages.AWAITING_PAYMENT: (
                Notification.PENDING_PAYMENT,
                Notification.PENDING_PAY),

            PurchaseStages.BUYER_PENDING: (
                Notification.PENDING_BUYER_CONFIRMATION,
                Notification.PENDING_BUY_CONFIRM),

            PurchaseStages.SELLER_PENDING: (
                Notification.PENDING_SELLER_CONFIRM,
                Notification.PENDING_SELLER_CONFIRMATION),

            PurchaseStages.IN_DISPUTE: (
                Notification.SELLER_DISPUTE,
                Notification.BUYER_DISPUTE),

            PurchaseStages.REVIEW_PERIOD: (
                Notification.SELLER_REVIEW,
                Notification.BUYER_REVIEW)
        }.get(PurchaseStages(int(purchase_obj.stage)), (None, None))

        if seller_notification or buyer_notification:
            listing_obj = Listing.query.filter_by(
                contract_address=purchase_obj.listing_address).first()
            if listing_obj:
                listing_params = listing_info(listing_obj)
                seller_notification and send_event_notification(
                    listing_obj.owner_address, seller_notification, **listing_params)
                buyer_notification and send_event_notification(
                    purchase_obj.buyer_address, buyer_notification, **listing_params)

    @classmethod
    def notify_listing(cls, listing_obj):
        listing_params = listing_info(listing_obj)
        send_event_notification(
            listing_obj.owner_address,
            Notification.LIST,
            **listing_params)

    @classmethod
    def notify_listing_update(cls, listing_obj):
        listing_params = listing_info(listing_obj)
        send_event_notification(
            listing_obj.owner_address,
            Notification.UPDATED,
            **listing_params)

    @classmethod
    def notify_review(cls, review_obj):
        # TODO(gagan): implement
        pass
