# 🚀 Bitcoin Node on Modal

This project deploys a **Bitcoin full node** on **Modal**, leveraging **serverless infrastructure** to manage blockchain data, provide RPC services, and enable remote access via tunnels.

## 🎯 Overview
- **Deploys a Bitcoin full node** in a **serverless environment**.
- Uses **Modal Tunnels** to expose the Bitcoin RPC server securely.
- Provides **Bitcoin JSON-RPC API** for querying blockchain data.
- Uses **Modal Volumes** to persist blockchain state across container restarts.
- Supports **automated deployments and function execution**.

## 🛠️ Tech Stack
- **Bitcoin Core**: Full node implementation for syncing the blockchain.
- **Modal**: Serverless infrastructure for running the Bitcoin node and RPC services.
- **Requests (Python)**: For making JSON-RPC calls to the Bitcoin node.
- **Modal Volumes**: Persistent storage for blockchain data.
- **Modal Tunnels**: Secure, dynamic public access to the RPC service.
- **Docker**: Custom-built Bitcoin Core image for Modal deployment.

## 🔥 Services & Features
### 1️⃣ **Bitcoin Node Deployment**
   - Starts a **Bitcoin full node** on Modal.
   - **Persists blockchain data** using **Modal Volumes**.
   - Stores the **tunnel URL in a shared volume** for RPC access.

### 2️⃣ **Bitcoin JSON-RPC Service**
   - Provides an RPC interface for **retrieving blockchain data**.
   - Queries supported:
     - **get_latest_block** → Retrieves the latest block details.
     - **get_block_count** → Fetches the latest blockchain height.

### 3️⃣ **Modal Tunnel for Remote Access**
   - Uses **`modal.forward(8332, unencrypted=True)`** to expose the RPC port.
   - The **tunnel URL** is dynamically stored in a **Modal Volume**.
   - Other functions fetch the **latest tunnel URL** to interact with Bitcoin RPC.

### 4️⃣ **Automated Function Execution**
   - **run_bitcoind** → Starts the Bitcoin node and exposes RPC.
   - **get_latest_block** → Fetches the latest block details via RPC.
   - **get_block_count** → Returns the current blockchain height.

## 🚀 Deployment & Usage
### 1️⃣ **Deploy to Modal**
Ensure Modal is set up and authenticated:
```sh
modal deploy test.py
```

### 2️⃣ **Start the Bitcoin Node**
Run the node and expose RPC:
```sh
modal run test.py::run_bitcoind
```
- ✅ This starts `bitcoind` in the **background**.
- ✅ Creates a **tunnel** and **saves the tunnel URL** to a **Modal Volume**.

### 3️⃣ **Retrieve Blockchain Data**
**Get the latest block count:**
```sh
modal run test.py::get_block_count
```

**Get the latest block details:**
```sh
modal run test.py::get_latest_block
```

### 4️⃣ **Query via cURL (Using Modal Tunnel)**
Once `run_bitcoind` is running, you can **query the Bitcoin node directly**:
```sh
curl --user bitcoinrpc:supersecurepassword --data-binary \
'{"jsonrpc": "1.0", "id": "curltest", "method": "getblockchaininfo", "params": []}' \
-H 'content-type: text/plain;' \
"https://your-modal-tunnel-url"
```
🔹 **Replace `your-modal-tunnel-url` with the actual tunnel URL stored in Modal Volume.**  
🔹 You can retrieve the latest tunnel URL by running:
```sh
modal run test.py::get_latest_block
```
  
## ⚠️ Known Issues
- **Dynamic Tunnel URL**: Each deployment generates a **new tunnel URL**, requiring updates in the querying scripts.
- **Auto-Restart on Function Calls**: Running RPC queries via `modal run` may trigger a **new container**, restarting the node.
- **Long Blockchain Sync Time**: Syncing the full Bitcoin blockchain on a serverless environment may take considerable time.

## 📌 Future Improvements
- **Persistent Bitcoin node without automatic restarts.**
- **Pre-synced blockchain state for faster node startup.**
- **Secure authentication for public RPC access.**

