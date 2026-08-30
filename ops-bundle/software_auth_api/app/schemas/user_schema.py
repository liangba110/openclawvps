from pydantic import BaseModel, Field

class RegisterSchema(BaseModel):
    username: str = Field(min_length=3, max_length=20, description="登录账号")
    password: str = Field(min_length=6, max_length=32, description="登录密码")

class LoginSchema(BaseModel):
    username: str
    password: str

class TokenSchema(BaseModel):
    token: str
