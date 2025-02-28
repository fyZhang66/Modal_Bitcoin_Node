import modal
import time
import os
import requests

app = modal.App(name="fy-bitcoin-node")

# ✅ Define the volume for storing Bitcoin data
bitcoin_data_vol = modal.Volume.from_name("bitcoin-fy-data")

# ✅ Define the Docker image for running bitcoind
bitcoind_image = modal.Image.from_dockerfile("./Dockerfile")

# ✅ RPC config
rpc_user = "bitcoinrpc"
rpc_password = "supersecurepassword"

# common function params
function_params = {
    "image": bitcoind_image,
    "volumes": {"/root/.bitcoin": bitcoin_data_vol},
}

# ✅ read tunnel url
def read_tunnel_url():
    bitcoin_data_vol.reload()  # ✅ make sure the volume is up-to-date
    with open("/root/.bitcoin/tunnel_url.txt", "r") as f:
        rpc_url = f.read().strip()
        print(f"✅ Readed Tunnel URL: {rpc_url}")
    return rpc_url

# ✅ send rpc request
def send_rpc_request(rpc_url, method, params=[]):
    response = requests.post(
        rpc_url,
        auth=(rpc_user, rpc_password),
        json={
            "jsonrpc": "1.0",
            "id": method,
            "method": method,
            "params": params
        }
    )
    return response

@app.function(
    image=bitcoind_image,
    volumes={"/root/.bitcoin": bitcoin_data_vol},
    timeout=60 * 60 * 24,  # longest timeout
    keep_warm=1,           # keep warm for 1 hour
)
def run_bitcoind():
    with modal.forward(8332, unencrypted=True) as tunnel:
        print(f"🔗 Tunnel URL: {tunnel.url}")
        print(f"🔌 Tunnel TLS Socket: {tunnel.tls_socket}")


        # ✅ save tunnel url to a file
        with open("/root/.bitcoin/tunnel_url.txt", "w") as f:
            f.write(tunnel.url)
            
        bitcoin_data_vol.commit()
        
        # ✅ background run bitcoind, prevent blocking thread
        os.system("bitcoind -server=1 -printtoconsole -conf=/root/.bitcoin/bitcoin.conf &")

        # ✅ Keep main thread alive, so the function doesn't exit
        while True:
            print("✅ bitcoind is running...")
            time.sleep(60)


@app.function(**function_params)
def get_latest_block():
    rpc_url = read_tunnel_url()
    response = send_rpc_request(rpc_url, "getbestblockhash")
    best_block_hash = response.json().get("result")

    if best_block_hash:
        response = send_rpc_request(rpc_url, "getblock", [best_block_hash, 2])
        print(response.json())
        return response.json()

    return {"error": "Failed to fetch block hash"}

@app.function(**function_params)
def get_block_count():
    rpc_url = read_tunnel_url()
    response = send_rpc_request(rpc_url, "getblockcount")
    # ✅ parse response
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
