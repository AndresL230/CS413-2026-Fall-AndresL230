"""RPC error type and the documented error codes."""

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
LAMBDA_SYNTAX_ERROR = -32010
LAMBDA_TYPE_ERROR = -32011
LAMBDA_TIMEOUT = -32012
LAMBDA_RUNTIME_ERROR = -32013

STANDARD_MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
}


class RpcError(Exception):
    """An error that maps directly to a JSON-RPC error object."""

    def __init__(self, code, message=None, data=None):
        super().__init__(message or STANDARD_MESSAGES.get(code, ""))
        self.code = code
        self.message = message if message is not None else STANDARD_MESSAGES[code]
        self.data = data

    def to_error_object(self):
        err = {"code": self.code, "message": self.message}
        if self.data is not None:
            err["data"] = self.data
        return err


def invalid_params(reason, param=None, **extra):
    data = {}
    if param is not None:
        data["param"] = param
    data["reason"] = reason
    data.update(extra)
    return RpcError(INVALID_PARAMS, data=data)
