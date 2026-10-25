# Solo-mining Radthal (ckpool)

🇫🇷 [Version française](MINER.md) (the reference text: if the two ever differ, the French one wins)

Radthal is mined with SHA-256: a Bitcoin ASIC miner (Avalon, Antminer, Bitaxe…) works. It does not plug directly into the node: it goes
through **ckpool**, a small mining server that runs next to the node. In "solo" mode, when your miner finds a block, **98% of the reward
goes to your `rdt1…` address** and **2% to the project creator's address** (a network rule from block 25,000 on, see "The developer
share" in the [README](README.en.md#the-developer-share-2)). `ckpool` handles this split by itself.

The more honest miners there are, the harder the chain is to rewrite: mining really helps the network.

> This recipe is the project creator's own (Linux, Docker, node and ckpool on the same machine, in "host network" mode).
> It replaces the `docker compose` installation of the README: do not run both on the same machine, they use the same port 9333.

## Before you start

- The commands are typed on the Linux machine that will run the node, in this repository's folder.
- You need the address of a running Radthal node (see "Known nodes" in the README). Without a connection to another node, Bitcoin
  Core refuses to hand out work to miners.
- Never make port **3333** (miners) or **8332** (RPC) reachable from the internet. Only **9333** may be.

## 1. The node

```bash
docker build -t radthal .
mkdir -p ~/radthal-data
```

Create the file `~/radthal-data/bitcoin.conf` (replace the password and the node address):

```bash
cat > ~/radthal-data/bitcoin.conf <<'CONF'
server=1
rpcuser=radthal
rpcpassword=CHOOSE-A-LONG-PASSWORD
dnsseed=0
fixedseeds=0
addnode=NODE_ADDRESS:9333
maxtipage=315360000
minimumchainwork=000000000000000000000000000000000000000000000000278424e424e42244
CONF
sudo chown -R 1000:1000 ~/radthal-data && sudo chmod 600 ~/radthal-data/bitcoin.conf
```

Start the node:

```bash
docker run -d --name radthal --restart unless-stopped --network host -v ~/radthal-data:/data radthal
```

Wait a few minutes, then check: `docker exec radthal radthal-cli getconnectioncount` should print 1 or more, and
`docker exec radthal radthal-cli getblockchaininfo` should show `blocks` catching up with the chain.

## 2. Your receiving address

```bash
docker exec radthal radthal-cli createwallet minage
docker exec radthal radthal-cli -rpcwallet=minage getnewaddress
```

Write the address down (it starts with `rdt1`). Back up the wallet (see the README, "Create a wallet").

## 3. ckpool

```bash
docker build -t ckpool -f mining/Dockerfile.ckpool mining
cp mining/ckpool.conf.example ~/ckpool.conf
nano ~/ckpool.conf
```

In `~/ckpool.conf`, replace `MOT_DE_PASSE_RPC` (the example file's placeholder for the RPC password) with the password from
`bitcoin.conf`, and `rdt1_TON_ADRESSE` (the placeholder for your address) with your address. Keep everything else as it is, in
particular the line `"donation": 2`: it is the developer share, **mandatory from block 25,000** (the `ckpool` in this repository
forces it to at least 2%, but the file might as well say so). Then:

```bash
mkdir -p ~/ckpool-logs
docker run -d --name ckpool --restart unless-stopped --network host \
  -v ~/ckpool.conf:/ckpool.conf:ro -v ~/ckpool-logs:/ckpool/logs ckpool
docker logs ckpool --tail 20
```

## 4. The miner

In your miner's web interface, set up a server (pool):

| Field | Value |
|---|---|
| URL | `stratum+tcp://YOUR_MACHINES_IP_ADDRESS:3333` |
| User | your `rdt1…` address (you can add `.name` after it, e.g. `rdt1….avalon1`) |
| Password | `x` |

When the miner finds a block, `docker logs ckpool` prints `BLOCK ACCEPTED`.

## Good to know

- **The `maxtipage=315360000` line is essential for a miner.** Bitcoin Core considers itself in "initial sync" as soon as its latest
  block is more than 24 hours old, and in that case it refuses to hand out work to ckpool (message
  `Bitcoin Core is in initial sync and waiting for blocks...` then `No bitcoinds active!`). On Bitcoin this never happens; on a small
  chain, a power cut or a miner left off for more than a day is enough, and nobody can mine the next block any more. This line turns
  that block off. If your node is already running without it: add it to `bitcoin.conf`, then `docker restart -t 120 radthal` (and
  `docker restart ckpool` if the miners do not come back by themselves). The `minimumchainwork=000000000000000000000000000000000000000000000000278424e424e42244` line goes with it:
  without it, a brand-new node would never consider itself "syncing" while it downloads the chain. With it, the node stays in sync mode
  until it has caught up to that cumulative-work level (value taken on 25 October 2026 from a block about 1,000 blocks below the tip),
  then `maxtipage` takes over. Never set a value higher than your chain's: the node would stay in "syncing" forever.
- **Before block 25,000: rebuild the `ckpool` image and update the node** (`docker build -t radthal .` and
  `docker build -t ckpool -f mining/Dockerfile.ckpool mining`, then recreate both containers with the commands above). Without this,
  your blocks would be rejected by up-to-date nodes from block 25,000 on.
- After a long stop, the difficulty does not change right away: it only readjusts at the next 2016-block step, and will then drop a
  little, since the period will have looked slow.
- The difficulty adjusts every 2016 blocks, like Bitcoin: a small miner can wait a long time before finding a block while the
  difficulty is high. This is lottery mining.
- Mined blocks can only be spent after 100 confirmations (Bitcoin rule).
- If blocks stop coming although the miner is running, first look at `docker logs ckpool --tail 50` and
  `docker logs radthal --tail 50`. Also turn on monitoring (README, "Monitoring and alerts").
