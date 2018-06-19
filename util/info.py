from .ipfs import hex_to_base58, IPFSHelper
from hexbytes import HexBytes
from io import BytesIO
import base64
from web3 import Web3

thumb_size = (256, 256)

def get_eth_price(hex=None, int=None):
    if hex:
        return str(Web3.fromWei(Web3.toInt(HexBytes(hex)), 'ether'))
    elif int:
        return str(Web3.fromWei(int, 'ether'))
    else:
        raise Exception("Please give either a hex or int amount")


def get_ipfs_data(ipfs_hash, with_thumbnails = False, root = 'data'):
    ipfs_hash = hex_to_base58(ipfs_hash)
    # Load IPFS data. Note: we filter out pictures since those should
    # not get persisted in the database.
    data =  IPFSHelper().file_from_hash(ipfs_hash,
                    root_attr=root,
                    exclude_fields=['pictures'])
    data["ipfs"] = ipfs_hash
    return data

def get_listing(contract_helper, listing_address):
    caller = contract_helper.get_instance("Listing", listing_address).call()

    ipfs_hash = caller.ipfsHash()
    data = get_ipfs_data(ipfs_hash)

    data["type"] = "Listing"
    data["owner"] = caller.owner()
    data["address"] = listing_address
    data["units"] = caller.unitsAvailable()
    data["price"] = get_eth_price(caller.price())
    return data

def get_create(ipfs_hash, price, units):
    data = get_ipfs_data(ipfs_hash)
    data["type"] = "preListing"
    data["units"] = units
    data["price"] = get_eth_price(price)
    return data

