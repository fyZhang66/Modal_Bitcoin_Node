# FROM python:3.9-slim

# ENV DEBIAN_FRONTEND=noninteractive

# RUN apt-get update && \
#     apt-get install -y \
#     autoconf \
#     automake \
#     build-essential \
#     cmake \
#     git \
#     libboost-chrono-dev \
#     libboost-dev \
#     libboost-filesystem-dev \
#     libboost-system-dev \
#     libboost-test-dev \
#     libboost-thread-dev \
#     libevent-dev \
#     libminiupnpc-dev \
#     libqt5core5a \
#     libqt5dbus5 \
#     libqt5gui5 \
#     libqt5widgets5 \
#     libsqlite3-dev \
#     libtool \
#     libzmq3-dev \
#     pkg-config \
#     qttools5-dev-tools && \
#     ln -s /usr/bin/python3 /usr/bin/python && \
# rm -rf /var/lib/apt/lists/*


# # 然后再继续
# RUN pip install --upgrade pip wheel uv

# RUN git clone --branch v25.0 --depth=1 https://github.com/bitcoin/bitcoin.git /opt/bitcoin
# WORKDIR /opt/bitcoin

# RUN cmake -B build \
#     -DBUILD_GUI=OFF \
#     -DENABLE_WALLET=OFF \ 
#     -DENABLE_BENCH=OFF \
#     -DENABLE_TESTS=OFF \
#     -DWITH_QRENCODE=OFF .
# RUN cmake --build build --target all -- -j4

# EXPOSE 8333 8332

# # We'll just define default command to run bitcoind
# CMD ["/opt/bitcoin/build/src/bitcoind", "-server=1", "-printtoconsole"]


FROM python:3.9-slim

ENV BITCOIN_VERSION=24.0.1
# 可根据需要修改版本

RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip && pip install fastapi[standard] uvicorn requests
RUN pip install requests
RUN wget https://bitcoin.org/bin/bitcoin-core-27.0/bitcoin-27.0-x86_64-linux-gnu.tar.gz \
    && tar -xzf bitcoin-27.0-x86_64-linux-gnu.tar.gz -C /usr/local --strip-components=1 \
    && rm bitcoin-27.0-x86_64-linux-gnu.tar.gz

EXPOSE 8333 8332
CMD ["bitcoind", "-server=1", "-printtoconsole"]


