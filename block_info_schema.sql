CREATE DATABASE IF NOT EXISTS bitcoin;
USE bitcoin;

-- Table storing general information about a Bitcoin block
CREATE TABLE IF NOT EXISTS bitcoin_block (
    hash VARCHAR(64) PRIMARY KEY,
    confirmations INTEGER,
    height INTEGER,
    version INTEGER,
    versionHex VARCHAR(16),
    merkleroot VARCHAR(64),
    time INTEGER,
    mediantime INTEGER,
    nonce INTEGER,
    bits VARCHAR(16),
    difficulty REAL,
    chainwork VARCHAR(255),
    nTx INTEGER,
    previousblockhash VARCHAR(64),
    strippedsize INTEGER,
    size INTEGER,
    weight INTEGER
);

-- Table storing Bitcoin transactions
CREATE TABLE IF NOT EXISTS transaction (
    txid VARCHAR(64) PRIMARY KEY,
    block_hash VARCHAR(64),
    hash VARCHAR(64),
    version INTEGER,
    size INTEGER,
    vsize INTEGER,
    weight INTEGER,
    locktime INTEGER,
    FOREIGN KEY (block_hash) REFERENCES bitcoin_block(hash)
);

-- Table storing transaction inputs
CREATE TABLE IF NOT EXISTS vin (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    txid VARCHAR(64),
    coinbase TEXT,
    sequence INTEGER,
    FOREIGN KEY (txid) REFERENCES transaction(txid)
);

-- Table storing witness data for SegWit-enabled transactions
CREATE TABLE IF NOT EXISTS vin_witness (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    vin_id INTEGER,
    witness TEXT,
    FOREIGN KEY (vin_id) REFERENCES vin(id)
);

-- Table storing transaction outputs
CREATE TABLE IF NOT EXISTS vout (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    txid VARCHAR(64),
    value REAL,
    n INTEGER,
    FOREIGN KEY (txid) REFERENCES transaction(txid)
);

-- Table storing locking script details for Bitcoin transaction outputs
CREATE TABLE IF NOT EXISTS script_pubkey (
    vout_id INTEGER PRIMARY KEY,
    asm TEXT,
    description TEXT,  -- Fixed `desc` naming issue
    hex TEXT,
    address VARCHAR(100),
    type VARCHAR(50),
    FOREIGN KEY (vout_id) REFERENCES vout(id)
);
