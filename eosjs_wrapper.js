class RpcWrapper {
    constructor(rpc) {
        this.rpc = rpc;
    }

    async get_info() {
        try {
            return await this.rpc.get_info();
        } catch (err) {
            return {error: err};
        }
    }

    async get_account(account) {
        try {
            return await this.rpc.get_account(account);
        } catch (err) {
            return {error: err};
        }
    }

    async get_code(account) {
        try {
            return await this.rpc.get_code(account);
        } catch (err) {
            return {error: err};
        }
    }

    async get_currency_balance(token_account, account, token_name) {
        try {
            return await this.rpc.get_currency_balance(token_account, account, token_name);
        } catch (err) {
            return {error: err};
        }
    }

    async get_producer_schedule() {
        try {
            return await this.rpc.get_producer_schedule();
        } catch (err) {
            return {error: err};
        }
    }

    async get_producers(json, lowerBound , limit) {
        try {
            return await this.rpc.get_producers(json, lowerBound, limit);
        } catch (err) {
            return {error: err};
        }
    }
    async get_table_rows(
        json = true,
        code,
        scope,
        table,
        lower_bound = '',
        upper_bound = '',
        index_position = 1,
        key_type = '',
        limit = 10,
        reverse = false,
        show_payer = false,
    ) {
        try {
            return await this.rpc.get_table_rows({
                json: json,
                code: code,
                scope: scope,
                table: table,
                lower_bound: lower_bound,
                upper_bound: upper_bound,
                index_position: index_position,
                key_type: key_type,
                limit: limit,
                reverse: reverse,
                show_payer: show_payer,
            }
            );
        } catch (err) {
            return {error: err};
        }
    }
}


class ApiWrapper {
    constructor(rpc, signatureProvider) {
      this.rpc = rpc;
      this.signatureProvider = signatureProvider;
      this.api = new eosjs_api.Api({ 'rpc': rpc, 'signatureProvider': signatureProvider });
    }

    jsonToRawAbi(abi) {
        try {
            return this.api.jsonToRawAbi(abi);
        } catch (err) {
            return {error: err};
        }
    }

    async transact (transaction, _a) {
        try {
            return await this.api.transact(transaction, _a);
        } catch (err) {
            return {'error': err};
        }
    }
}

window.output_buffer = '';

function compile_src(src) {
    code_ptr = mp_js_compile_src(src);
    // console.log(code_ptr);
    if (code_ptr == 0) {
        return 0;
    }
    code_size = getValue(code_ptr, 'i32');
    // console.log(code_size);
    var hexString = '';
    for (var i=0;i<code_size;i++) {
        var b = getValue(code_ptr + 4 + i, 'i8');
        b &= 0xff;
        var hex = b.toString(16);
        if (hex.length == 1) {
            hex = '0'+hex;
        }
        hexString += hex;
    }
    // console.log(hexString);
    return hexString;
}

window.ApiWrapper = ApiWrapper;
window.RpcWrapper = RpcWrapper;

