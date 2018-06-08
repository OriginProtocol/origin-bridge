import re
import hexbytes
from .contract import get_contract_internal_name, ContractHelper, get_contract_link_name
from web3 import Web3
from eth_abi import decode_abi

LINKER_NAME_MATCH = re.compile("__([a-zA-Z0-9]{1,37})_+")

CONTRACTS_LIBRARIES_SPACE = {}
SIG_DICTS = {}

def _parse_abi_params(abi_entity, key):
    return [(i["type"], i["name"]) for i in abi_entity[key]] # strip out the _ that comes with the keys for some reason

def _parse_abi_inputs(abi_entity):
    return _parse_abi_params(abi_entity, "inputs")

def _parse_abi_outputs(abi_entity):
    return _parse_abi_params(abi_entity, "outputs")

def extract_libraries(byte_code):
    return dict((link_match.group(1), (link_match.start(), link_match.end())) for link_match in LINKER_NAME_MATCH.finditer(byte_code))

def match_link_code(bytecode, contract_bytecode, libraries):
    lib_map = {}
    out_buffer = ""
    last_end = 0
    if bytecode.startswith("0x73"):
        out_buffer = "0x73" + "0"*40
        last_end = 44
    for name, (start, end) in libraries.items():
        linked_address = bytecode[start:end]
        if not linked_address:
            #no match abort
            return False, {}
        else:
            lib_map[name] = "0x" + linked_address
        #throw in the placeholder for matching
        out_buffer += bytecode[last_end:start] + get_contract_internal_name(name)
        last_end = end
    out_buffer += bytecode[last_end:]
    return out_buffer == contract_bytecode, lib_map

def _get_code(web3, address):
    return hexbytes.HexBytes(web3.eth.getCode(Web3.toChecksumAddress(address))).hex()

def match_address_to_bytecode(web3, address, contract_bytecode, libraries, contracts_space, bytecode = None):
    if not bytecode:
        bytecode = _get_code(web3, address)
    match, linked_addresses = match_link_code(bytecode, contract_bytecode, libraries)
    if match:
        if linked_addresses:
            for short_name, linked_address in linked_addresses.items():
                if short_name in contracts_space:
                    name, contract_code, libraries = contracts_space[short_name]
                    if not match_address_to_bytecode(web3, linked_address, contract_code, libraries, contracts_space):
                        return False
                else:
                    return False
        return True


def _find_address_contract(web3, address, contracts_space):
    bytecode = _get_code(web3, address)
    for short_name, (name, contract_code, libraries) in contracts_space.items():
        if match_address_to_bytecode(web3, address, contract_code, libraries, contracts_space, bytecode):
            return name

def _generate_contract_space():
    if not CONTRACTS_LIBRARIES_SPACE:
        for contract in ContractHelper.get_all_contracts():
            bytecode = ContractHelper.get_contract_deployed_bytecode(contract)
            CONTRACTS_LIBRARIES_SPACE[get_contract_link_name(contract)] = (contract, bytecode, extract_libraries(bytecode))

def match_address_contract(web3, address, name):
    _generate_contract_space()
    (name, contract_code, libraries) = CONTRACTS_LIBRARIES_SPACE[get_contract_link_name(name)]
    return match_address_to_bytecode(web3, address, contract_code, libraries, CONTRACTS_LIBRARIES_SPACE)

def find_address_contract(web3, address):
    _generate_contract_space()
    return _find_address_contract(web3, address, CONTRACTS_LIBRARIES_SPACE)


def _extract_abi_signatures(contract):
    # check chace for dict first
    if contract in SIG_DICTS:
        return SIG_DICTS[contract]
    abi = ContractHelper.get_contract_abi(contract)
    sig_dict = {}
    for abi_ent in abi:
        if "name" in abi_ent:
            name = abi_ent["name"]
            signature = Web3.sha3(text = name + "(" + ",".join([e[0] for e in _parse_abi_inputs(abi_ent)]) + ")").hex()
            abi_ent["sig"] = signature # take first 4 bytes as key
            sig_dict[signature[2:10]] = abi_ent
    # cache it
    SIG_DICTS[contract] = sig_dict
    return sig_dict

def extract_contract_call(data, contract):
    sig_dict = _extract_abi_signatures(contract)
    call_hash = data[2:10] # skip the 0x and grab the first 4 bytes
    params = data[10:]
    if call_hash in sig_dict:
        abi_ent = sig_dict[call_hash]
        input_fields = _parse_abi_inputs(abi_ent)
        input_values = decode_abi([i[0] for i in input_fields], hexbytes.HexBytes(params))
        return abi_ent["name"], dict(zip([i[1] for i in input_fields], input_values))
