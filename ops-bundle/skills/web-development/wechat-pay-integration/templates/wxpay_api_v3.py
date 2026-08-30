"""
微信支付 API v3 集成模块 — JSAPI / NATIVE / H5 / 退款 / 回调验签+解密
来源：/opt/ttdazi/payment_service/wxpay.py（生产已验证，2026-08）
新站点接入：复制本文件，替换配置；服务端语言为 Node 时按同逻辑移植（签名串/AES-GCM 不变）。
"""
import json, time, hashlib, random
from urllib.request import Request, urlopen

# ============ 配置（新站点：替换为本站值；本项目商户配置见 references/merchant-and-architecture.md）============
WX_APPID = '<公众号APPID>'
WX_MCHID = '<商户号>'
WX_API_KEY_V3 = '<API v3 密钥>'          # 商户平台设置
WX_NOTIFY_URL = 'https://<本站域名>/<回调路径>'   # ⚠️ 每个站点独立回调域名（notify_url 是下单参数）

CERT_DIR = '<证书目录>'   # apiclient_key.pem / apiclient_cert.pem / wx_platform_cert.pem
with open(f'{CERT_DIR}/apiclient_key.pem', 'r') as f:
    WX_PRIVATE_KEY = f.read()

# ============ 工具函数 ============

def _get_serial_no():
    """读取商户证书序列号"""
    import subprocess
    r = subprocess.run(
        ['openssl', 'x509', '-in', f'{CERT_DIR}/apiclient_cert.pem',
         '-noout', '-serial'],
        capture_output=True, text=True)
    serial = r.stdout.strip().replace('serial=', '')
    return serial


def _build_token(method: str, url_path: str, body: str = '') -> str:
    """生成 APIv3 认证 Token：WECHATPAY2-SHA256-RSA2048 mchid/nonce_str/serial_no/signature/timestamp"""
    timestamp = str(int(time.time()))
    nonce = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=32))
    message = f'{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n'   # 签名串格式

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    private_key = serialization.load_pem_private_key(
        WX_PRIVATE_KEY.encode(), password=None, backend=default_backend())
    signature = private_key.sign(
        message.encode(), padding.PKCS1v15(), hashes.SHA256())
    sign_b64 = __import__('base64').b64encode(signature).decode()

    serial_no = _get_serial_no()
    return (
        f'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{WX_MCHID}",'
        f'nonce_str="{nonce}",'
        f'serial_no="{serial_no}",'
        f'signature="{sign_b64}",'
        f'timestamp="{timestamp}"'
    )


def _wx_request(method: str, path: str, body: dict = None) -> dict:
    """调用微信支付 APIv3"""
    url = f'https://api.mch.weixin.qq.com{path}'
    body_str = json.dumps(body, ensure_ascii=False) if body else ''
    token = _build_token(method, path, body_str)

    req = Request(url, data=body_str.encode() if body else None, method=method)
    req.add_header('Authorization', token)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')

    try:
        resp = urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'code': 'FAIL', 'message': str(e)}


# ============ 支付接口 ============

def jsapi_pay(openid: str, out_trade_no: str, amount: int,
              description: str, attach: str = '') -> dict:
    """JSAPI 支付（公众号内）。amount: 分。返回 prepay_id，前端调起支付"""
    body = {
        'appid': WX_APPID,
        'mchid': WX_MCHID,
        'description': description,
        'out_trade_no': out_trade_no,
        'notify_url': WX_NOTIFY_URL,
        'amount': {'total': amount, 'currency': 'CNY'},
        'payer': {'openid': openid},
        'attach': attach
    }
    return _wx_request('POST', '/v3/pay/transactions/jsapi', body)


def native_pay(out_trade_no: str, amount: int, description: str,
               attach: str = '') -> dict:
    """Native 扫码支付。返回 code_url（二维码链接）"""
    body = {
        'appid': WX_APPID,
        'mchid': WX_MCHID,
        'description': description,
        'out_trade_no': out_trade_no,
        'notify_url': WX_NOTIFY_URL,
        'amount': {'total': amount, 'currency': 'CNY'},
        'attach': attach
    }
    return _wx_request('POST', '/v3/pay/transactions/native', body)


def h5_pay(out_trade_no: str, amount: int, description: str,
           attach: str = '') -> dict:
    """H5 支付（手机浏览器）。返回 h5_url"""
    body = {
        'appid': WX_APPID,
        'mchid': WX_MCHID,
        'description': description,
        'out_trade_no': out_trade_no,
        'notify_url': WX_NOTIFY_URL,
        'amount': {'total': amount, 'currency': 'CNY'},
        'scene_info': {'payer_client_ip': '<服务器IP>', 'h5_info': {'type': 'Wap'}},
        'attach': attach
    }
    return _wx_request('POST', '/v3/pay/transactions/h5', body)


def query_order(out_trade_no: str) -> dict:
    """查询订单"""
    return _wx_request(
        'GET', f'/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={WX_MCHID}')


def close_order(out_trade_no: str) -> dict:
    """关闭订单"""
    body = {'mchid': WX_MCHID}
    return _wx_request(
        'POST', f'/v3/pay/transactions/out-trade-no/{out_trade_no}/close', body)


def refund(out_trade_no: str, refund_no: str, amount: int, total: int,
           reason: str = '') -> dict:
    """退款"""
    body = {
        'out_trade_no': out_trade_no,
        'out_refund_no': refund_no,
        'amount': {'refund': amount, 'total': total, 'currency': 'CNY'},
        'reason': reason,
        'notify_url': WX_NOTIFY_URL.replace('/wxpay/notify', '/wxpay/refund_notify')
    }
    return _wx_request('POST', '/v3/refund/domestic/refunds', body)


def verify_notify(headers: dict, body: str) -> bool:
    """验证微信支付回调通知签名（平台证书公钥验 TIMESTAMP\\nNONCE\\nBODY\\n）"""
    try:
        timestamp = headers.get('Wechatpay-Timestamp', '')
        nonce = headers.get('Wechatpay-Nonce', '')
        signature = headers.get('Wechatpay-Signature', '')
        message = f'{timestamp}\n{nonce}\n{body}\n'

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64

        cert_file = f'{CERT_DIR}/wx_platform_cert.pem'   # 生产应缓存并按 Wechatpay-Serial 轮换
        with open(cert_file, 'rb') as f:
            cert = serialization.load_pem_x509_certificate(f.read(), default_backend())
        cert.public_key().verify(
            base64.b64decode(signature), message.encode(),
            padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def decrypt_notify_resource(resource: dict) -> dict:
    """AES-256-GCM 解密回调 resource（key=API v3 密钥，tag=密文末16字节）"""
    import json, base64
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    nonce = resource['nonce'].encode()
    ciphertext = base64.b64decode(resource['ciphertext'])
    tag = ciphertext[-16:]
    data = ciphertext[:-16]
    cipher = Cipher(algorithms.AES(WX_API_KEY_V3.encode()),
                    modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    decryptor.authenticate_additional_data(resource['associated_data'].encode())
    return json.loads((decryptor.update(data) + decryptor.finalize()).decode())
