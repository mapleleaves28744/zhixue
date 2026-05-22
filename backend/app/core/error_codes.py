from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0
    PARAM_ERROR = 40001
    REQUEST_BODY_ERROR = 40002
    UNAUTHORIZED = 40101
    TOKEN_EXPIRED = 40102
    FORBIDDEN = 40301
    NOT_FOUND = 40401
    CONFLICT = 40901
    BUSINESS_VALIDATION_ERROR = 42201
    TOO_MANY_REQUESTS = 42901
    INTERNAL_ERROR = 50001
    LLM_CALL_FAILED = 50002
    AGENT_RUN_FAILED = 50003
    FILE_PARSE_FAILED = 50004
    VECTOR_SEARCH_FAILED = 50005


ERROR_MESSAGES: dict[int, str] = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.REQUEST_BODY_ERROR: "请求体格式错误",
    ErrorCode.UNAUTHORIZED: "未登录或 Token 无效",
    ErrorCode.TOKEN_EXPIRED: "Token 已过期",
    ErrorCode.FORBIDDEN: "权限不足",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.CONFLICT: "资源冲突",
    ErrorCode.BUSINESS_VALIDATION_ERROR: "业务校验失败",
    ErrorCode.TOO_MANY_REQUESTS: "请求过于频繁",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
    ErrorCode.LLM_CALL_FAILED: "大模型调用失败",
    ErrorCode.AGENT_RUN_FAILED: "Agent 执行失败",
    ErrorCode.FILE_PARSE_FAILED: "文件解析失败",
    ErrorCode.VECTOR_SEARCH_FAILED: "向量检索失败",
}


HTTP_STATUS_BY_CODE: dict[int, int] = {
    ErrorCode.PARAM_ERROR: 400,
    ErrorCode.REQUEST_BODY_ERROR: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.BUSINESS_VALIDATION_ERROR: 422,
    ErrorCode.TOO_MANY_REQUESTS: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.LLM_CALL_FAILED: 500,
    ErrorCode.AGENT_RUN_FAILED: 500,
    ErrorCode.FILE_PARSE_FAILED: 500,
    ErrorCode.VECTOR_SEARCH_FAILED: 500,
}
