import modal

import os
import requests

app = modal.App(name="fy-bitcoin-node")

# 引用 Modal 上已有名为 "fy-bitcoin" 的 Volume
bitcoin_data_vol = modal.Volume.from_name("bitcoin-fy-data")

# 这里从同目录下的 Dockerfile 构建镜像（该 Dockerfile 用 wget 下载 bitcoin tarball 并解压）
bitcoind_image = modal.Image.from_dockerfile("./Dockerfile")

rpc_url = "https://3lozw8f1z7v595.r21.modal.host"
rpc_user = "bitcoinrpc"
rpc_password = "supersecurepassword"

@app.function(
    image=bitcoind_image,
    volumes={"/root/.bitcoin": bitcoin_data_vol},
    timeout=60 * 60 * 24,  # 最长允许跑 24 小时
    keep_warm=1,           # 保持容器预热(可选)
)
def run_bitcoind():
    with modal.forward(8332, unencrypted=True) as tunnel:
        print(f"🔗 Tunnel URL: {tunnel.url}")
        print(f"🔌 Tunnel TLS Socket: {tunnel.tls_socket}")
        
        # ✅ 直接在主线程上运行 bitcoind，不使用 subprocess
        os.execvp("bitcoind", [ 
            "bitcoind",
            "-server=1",
            "-printtoconsole",
            "-conf=/root/.bitcoin/bitcoin.conf",
        ])

# @app.function(image=bitcoind_image, volumes={"/root/.bitcoin": bitcoin_data_vol},)
# def get_tunnel_url():
#     try:
#         with open("/root/.bitcoin/xyz.txt", "r") as f:
#             tunnel_url = f.read().strip()
#             print(f"✅ 读取的 Tunnel URL: {tunnel_url}")
#             return tunnel_url
#     except FileNotFoundError:
#         print("⚠️ 文件不存在，无法读取 Tunnel URL！")

@app.function(image=bitcoind_image)
def get_latest_block():
    response = requests.post(
        rpc_url,
        auth=(rpc_user, rpc_password),
        json={
            "jsonrpc": "1.0",
            "id": "getbestblockhash",
            "method": "getbestblockhash",
            "params": []
        }
    )
    best_block_hash = response.json().get("result")

    if best_block_hash:
        response = requests.post(
            rpc_url,
            auth=(rpc_user, rpc_password),
            json={
                "jsonrpc": "1.0",
                "id": "getblock",
                "method": "getblock",
                "params": [best_block_hash, 2]
            }
        )
        print(response.json())
        return response.json()

    return {"error": "Failed to fetch block hash"}

@app.function(image=bitcoind_image)
def get_block_count():
    # ✅ 发送 RPC 请求
    payload = {
        "jsonrpc": "1.0",
        "id": "getblockcount",
        "method": "getblockcount",
        "params": []
    }
    response = requests.post(
            rpc_url,
            auth=(rpc_user, rpc_password),
            json=payload
        )

        # ✅ 解析结果
    if response.status_code == 200:
        block_height = response.json()["result"]
        print(f"✅ Latest Block Height: {block_height}")
        return block_height
    else:
        print(f"❌ RPC Error: {response.text}")
        return None

@app.local_entrypoint()
def main():
    print("Starting bitcoind in a Modal container...")
    bitcoind_future = run_bitcoind.spawn()
