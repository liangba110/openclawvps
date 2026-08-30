from pydantic import BaseModel, Field

class CreateOrderSchema(BaseModel):
    goods_type: int = Field(ge=1, le=4, description="1日卡 2月卡 3年卡 4永久")
    pay_type: str = Field(pattern="^(alipay|wechat)$", description="alipay/wechat")
