from browser import html, window, aio, ajax
import javascript

from . import config
from . import wallet
from .chaincache import ChainCache
import json

class ChainException(Exception):
    def __init__(self, err):
        super().__init__(err)
        self.error = err

    def __repr__(self):
        return javascript.JSON.stringify(self.error, None, ' ')

    def __str__(self):
        return javascript.JSON.stringify(self.error, None, ' ')

def jsobj2pyobj(fn):
    async def wrapper(self, *args, **kwargs):
        ret = await fn(self, *args, **kwargs)
        ret = javascript.jsobj2pyobj(ret)
        if ret and 'error' in ret:
            raise ChainException(ret.error)
        return ret
    return wrapper

class ChainApiAsync():
    def __init__(self, node_url = 'http://127.0.0.1:8888', network='EOS'):
        self.node_url = node_url
        self.network = network
        
        self._rpc = window.eosjs_jsonrpc.JsonRpc.new(node_url)
        self.rpc = window.RpcWrapper.new(self._rpc)
        self.api = window.ApiWrapper.new(self._rpc, wallet.signatureProvider)
        self.db = ChainCache(self, network)

    def set_node(self, node_url):
        self.node_url = node_url
        self._rpc.endpoint = node_url

    async def get_chain_id(self):
        info = await self.get_info()
        return info.chain_id

    @jsobj2pyobj
    async def get_info(self):
        return await self.rpc.get_info()

    @staticmethod
    def mp_compile(contract, code):
        code = window.compile_src(code)
        code = bytes.fromhex(code)
        assert code, 'compiler failed to compile code'
        mpy_code = ((code, len(code)),)

        code_region = b''
        code_size_region = b''
        for code, size in mpy_code:
            code_region += code
            code_size_region += int.to_bytes(size, 4, 'little')

        name_region = b'main.mpy\x00'

        region_sizes = b''
        region_sizes += int.to_bytes(len(name_region), 4, 'little')
        region_sizes += int.to_bytes(len(code_size_region), 4, 'little')
        region_sizes += int.to_bytes(len(code_region), 4, 'little')

        header = int.to_bytes(5, 4, 'little')
        header += bytearray(60)
        frozen_code = header + region_sizes + name_region + code_size_region + code_region
        return frozen_code

    def compile(self, contract, code, vm_type=1):
        assert vm_type == 1
        return self.mp_compile(contract, code)

    @jsobj2pyobj
    async def push_action(self, contract, action, args, permissions, compress=0):
        authorizations = []
        for actor in permissions:
            authorizations.append({
                'actor': actor,
                'permission': permissions[actor],
            })
        if isinstance(args, bytes):
            args = args.hex()
        action = {
            'account': contract,
            'name': action,
            'authorization': authorizations,
            'data': args,
        }
        return await self.api.transact({
            'actions': [action]
        }, {
            'blocksBehind': 3,
            'expireSeconds': 30,
        })

    @jsobj2pyobj
    async def get_account(self, account):
        ret = await self.rpc.get_account(account)
        if 'error' in ret:
            return None
        return ret

    @jsobj2pyobj
    async def get_code(self, account):
        return await self.rpc.get_account(account)

    @jsobj2pyobj
    async def create_account(self, creator, account, owner_key, active_key, ram_bytes=0, stake_net=0.0, stake_cpu=0.0, sign=True):
        actions = []
        args = {
            'creator': creator,
            'name': account,
            'owner': {
                'threshold': 1,
                'keys': [{'key': owner_key, 'weight': 1}],
                'accounts': [],
                'waits': []
            },
            'active': {
                'threshold': 1,
                'keys': [{'key': active_key, 'weight': 1}],
                'accounts': [],
                'waits': []
            }
        }

        act = {
            'account': config.system_contract,
            'name': 'newaccount',
            'authorization': [{
                'actor': creator,
                'permission': 'active',
            }],
            'data': args,
        }
        actions.append(act)

        if ram_bytes:
            args = {'payer':creator, 'receiver':account, 'bytes':ram_bytes}
            act = {
                'account': config.system_contract,
                'name': 'buyrambytes',
                'authorization': [{
                    'actor': creator,
                    'permission': 'active',
                }],
                'data': args,
            }
            actions.append(act)

        if stake_net or stake_cpu:
            args = {
                'from': creator,
                'receiver': account,
                'stake_net_quantity': '%0.4f %s'%(stake_net, config.main_token),
                'stake_cpu_quantity': '%0.4f %s'%(stake_cpu, config.main_token),
                'transfer': 1
            }
            act = {
                'account': config.system_contract,
                'name': 'delegatebw',
                'authorization': [{
                    'actor': creator,
                    'permission': 'active',
                }],
                'data': args,
            }
            actions.append(act)
        return await self.api.transact({
            'actions': actions
        }, {
            'blocksBehind': 3,
            'expireSeconds': 30,
        })

    async def get_balance(self, account, token_account=None, token_name=None):
        if not token_name:
            token_name = config.main_token
        if not token_account:
            token_account = config.main_token_contract
        try:
            ret = await self.rpc.get_currency_balance(token_account, account, token_name)
            return float(ret[0].split(' ')[0])
        except Exception as e:
            return 0.0
        return 0.0

    @jsobj2pyobj
    async def transfer(self, _from, to, amount, memo='', token_account=None, token_name=None, permission='active'):
        if not token_account:
            token_account = config.main_token_contract
        if not token_name:
            token_name = config.main_token
        args = {"from":_from, "to":to, "quantity":'%.4f %s'%(amount, token_name), "memo":memo}
        return await self.push_action(token_account, 'transfer', args, {_from:permission})

    @jsobj2pyobj
    async def deploy_contract(self, account, code, abi, vmtype=1, vmversion=0, sign=True, compress=0):
        actions = []
        same_code = code == self.db.get_code(account)
        if not same_code:
            args = {"account": account,
                    "vmtype": vmtype,
                    "vmversion": vmversion,
                    "code": code.hex()
            }
            setcode = {
                'account': config.system_contract,
                'name': 'setcode',
                'authorization': [{
                    'actor': account,
                    'permission': 'active',
                }],
                'data': args,
            }
            actions.append(setcode)

        if isinstance(abi, dict):
            abi = self.api.jsonToRawAbi(abi)
        elif isinstance(abi, str):
            abi = json.loads(abi)
            abi = self.api.jsonToRawAbi(abi)
        elif isinstance(abi, bytes):
            abi = abi.hex()

        same_abi = abi == self.db.get_abi(account)
        if not same_abi:
            args = {'account':account, 'abi':abi}
            setabi = {
                'account': config.system_contract,
                'name': 'setabi',
                'authorization': [{
                    'actor': account,
                    'permission': 'active',
                }],
                'data': args,
            }

            actions.append(setabi)

        if not actions:
            return None

        ret = await self.api.transact({
            'actions': actions
        }, {
            'blocksBehind': 3,
            'expireSeconds': 30,
        })

        if not same_code:
            self.db.set_code(account, code)

        if not same_abi:
            self.db.set_abi(account, abi)

        return ret

    @jsobj2pyobj
    async def get_table_rows(self, json,
                    code,
                    scope,
                    table,
                    table_key='',
                    lower_bound='',
                    upper_bound='',
                    limit=10,
                    key_type='',
                    index_position=1,
                    encode_type='dec'):

        return await self.rpc.get_table_rows(json, code, scope, table,
                                lower_bound,
                                upper_bound,
                                index_position,
                                key_type,
                                limit,
                                False,
                                False                                
                            )

    @jsobj2pyobj
    async def get_producer_schedule(self):
        return await self.rpc.get_producer_schedule()

    @jsobj2pyobj
    async def get_producers(self, json = True, lowerBound = '', limit = 50):
        return await self.rpc.get_producers(json, lowerBound, limit)

async def hello():
    url = 'http://127.0.0.1:8888'
    defaultPrivateKey = "5JRYimgLBrRLCBAcjHUWCYRv3asNedTYYzVgmiU4q2ZVxMBiJXL"
    rpc = window.eosjs_jsonrpc.JsonRpc.new(url)
    signatureProvider = window.eosjs_jssig.JsSignatureProvider.new([defaultPrivateKey])
    api = window.eosjs_api.Api.new({ 'rpc':rpc, 'signatureProvider':signatureProvider })
    r = await rpc.get_info()
    print(r)

    print(get_chain_id)

    action = {
        'account': 'uuos.token',
        'name': 'transfer',
        'authorization': [{
            'actor': 'hello',
            'permission': 'active',
        }],
        'data': {
            'from': 'hello',
            'to': 'uuos',
            'quantity': '0.0001 UUOS',
            'memo': '',
        },
    }
    result = await api.transact({
        'actions': [action]
    }, {
        'blocksBehind': 3,
        'expireSeconds': 30,
    })

    balance = await rpc.get_currency_balance('uuos.token', 'uuos', 'UUOS')
    print(balance)

    balance = await rpc.get_currency_balance('uuos.token', 'hello', 'UUOS')
    print(balance)


#print(javascript.py2js(on_get_info))

