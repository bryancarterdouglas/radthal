# Radthal : fork de Bitcoin Core v31.1
# Compile le code officiel de Bitcoin Core puis applique radthal.patch
# (nom, magic bytes, ports, prefixes d'adresses, bloc genesis).
#
#   docker build -t radthal .
#
# Compilation lente : de quelques dizaines de minutes (PC) a plus d'une heure
# (Raspberry Pi). Si la machine manque de memoire : --build-arg JOBS=1

FROM debian:bookworm-slim AS build
ARG BITCOIN_TAG=v31.1
ARG JOBS=2
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake pkgconf python3 libevent-dev libboost-dev libsqlite3-dev \
      git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch "${BITCOIN_TAG}" https://github.com/bitcoin/bitcoin.git .
COPY radthal.patch /tmp/radthal.patch
RUN git apply --check /tmp/radthal.patch && git apply /tmp/radthal.patch
RUN cmake -S . -B /build -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_GUI=OFF -DBUILD_TESTS=OFF -DBUILD_BENCH=OFF -DBUILD_TX=OFF \
      -DBUILD_UTIL=OFF -DBUILD_WALLET_TOOL=OFF -DENABLE_IPC=OFF -DWITH_ZMQ=OFF \
 && cmake --build /build -j"${JOBS}"

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      libevent-2.1-7 libevent-core-2.1-7 libevent-extra-2.1-7 libevent-pthreads-2.1-7 libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 radthal \
    && mkdir /data && chown radthal:radthal /data
# Verification rapide (avant de copier le programme) que les bibliotheques sont bien la
RUN ldconfig -p | grep -q 'libevent_pthreads-2.1.so.7' \
 && ldconfig -p | grep -q 'libevent_core-2.1.so.7' \
 && ldconfig -p | grep -q 'libsqlite3.so.0'
COPY --from=build /build/bin/bitcoind /build/bin/bitcoin-cli /usr/local/bin/
# Raccourci : radthal-cli <commande>  (equivaut a bitcoin-cli -datadir=/data <commande>)
RUN printf '#!/bin/sh\nexec bitcoin-cli -datadir=/data "$@"\n' > /usr/local/bin/radthal-cli \
 && chmod +x /usr/local/bin/radthal-cli \
 && if ldd /usr/local/bin/bitcoind | grep 'not found'; then exit 1; fi
USER radthal
VOLUME /data
EXPOSE 9333
CMD ["bitcoind", "-datadir=/data", "-printtoconsole"]
