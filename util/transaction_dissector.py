from .contract_reflection import match_address_contract, extract_contract_call, find_address_contract
from .contract import ContractHelper
from web3 import Web3
from .info import get_eth_price, get_listing, get_create, get_ipfs_data
import inspect
from hexbytes import HexBytes

from pprint import pprint
pout = open("dissect_out", "a")

CONTRACT_CALL_DISSECTORS = {}

def register_dissector(contract_dot_function):
    def __wrapped_decorator(function):
        CONTRACT_CALL_DISSECTORS[contract_dot_function] = function
        return function
    return __wrapped_decorator

def call_dissector(contract_dot_function, contract_helper, to, params):
    if contract_dot_function in CONTRACT_CALL_DISSECTORS:
        call = CONTRACT_CALL_DISSECTORS[contract_dot_function]
    else:
        call = _default_dissector
        params["contract_dot_function"] = contract_dot_function
    call_args = inspect.getargspec(call)[0]
    call_params = dict((k, params[k]) for k in call_args if k in params)
    return call(contract_helper, to, **call_params)

def dissect_transaction(current_rpc, txn_obj):
    print("REFLECT START", file =pout)
    print("txn_obj:", file=pout)
    pprint(txn_obj, stream=pout)
    # gas
    gas = Web3.toInt(HexBytes(txn_obj["gas"]))
    gas_price = Web3.toInt(HexBytes(txn_obj["gasPrice"]))
    # got the estimated gas cost
    gas_cost = get_eth_price(int = gas * gas_price)
    value_cost = get_eth_price(hex = txn_obj.get("value", "0x0"))

    to_address = Web3.toChecksumAddress(txn_obj["to"])
    data = txn_obj.get("data")

    meta = {"to":to_address, "gas":gas_cost, "value":value_cost}

    #grab meta data from contract and transaction
    if to_address and data:
        helper = ContractHelper(rpc = current_rpc)
        contract = find_address_contract(helper.web3, to_address)
        if contract:
            call, params = extract_contract_call(data, contract)
            dot_call = contract + "." + call
            meta["contract"] = contract
            meta["call"] = call
            meta["params"] = params
            print("call:", file=pout)
            pprint(dot_call, stream=pout)
            print("params:", file=pout)
            pprint(params, stream=pout)
            info = call_dissector(dot_call, helper, to_address, params)
            if info:
                meta["info"] = info
    print("meta:", file=pout)
    pprint(meta, stream=pout)
    print("REFLECT END", file =pout)
    pout.flush()
    return meta


@register_dissector("UnitListing.buyListing")
def buyListing(contractHelper, listingAddress, _unitsToBuy):
    data = get_listing(contractHelper, listingAddress)
    data["action"] = "purchase"
    data["unitsToBuy"] = _unitsToBuy
    return data

@register_dissector("ListingsRegistry.create")
def create(contractHelper, registryAddress, _ipfsHash, _price, _unitsAvailable):
    data = get_create(HexBytes(_ipfsHash), _price, _unitsAvailable)
    data["action"] = "list"
    return data

def _default_dissector(contractHelper, contractAddress, _ipfsHash = None, contract_dot_function =""):
    if _ipfsHash:
        data = get_ipfs_data(HexBytes(_ipfsHash), root=None)
    else:
        data = {}
    call = contract_dot_function.split(".")
    data["action"] = call[1] + " " + call[0]
    data["name"] = ""
    return data
    



