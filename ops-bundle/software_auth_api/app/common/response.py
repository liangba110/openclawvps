from typing import Any, Optional
from fastapi.responses import JSONResponse


def success(data: Any = None, msg: str = "操作成功", code: int = 200):
    return JSONResponse(status_code=200, content={"code": code, "msg": msg, "data": data})


def fail(msg: str = "操作失败", code: int = 400, data: Any = None):
    return JSONResponse(status_code=200, content={"code": code, "msg": msg, "data": data})
