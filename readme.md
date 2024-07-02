# COMP3221 A3 Blockchain - Group 20

## Prerequisites

Related packages to be installed in your local machine to run the program.

### Environment

WindowOS, MacOS
<br>
Tested on python version: 3.9.6

### Installation

Use the package manager `pip` to install the following packages.

```bash
pip install hashlib
pip install cryptography
```

If module not found error occurs like this,

```
John-Doe:ROOT-DIRECTORY johndoe$ python3 COMP3221_FLServer.py
Traceback (most recent call last):
  File "/Users/johndoe/folder/BlockchainNode.py", line 3, in <module>
    import hashlib
ModuleNotFoundError: No module named 'hashlib'
```

Please try the instructions below.

Open terminal, and enter `which python`.
Then, it will print the path of python in your machine like this.

```
/usr/bin/python
```

Copy the path, and try the command below in the terminal

```
/usr/bin/python -m pip install <package>
```

## Getting Started

### Assumptions

-   All files should be in the same level of directory in your machine

### Folder Structure

To run the program appropriately, the folder must follow the structure below.

```
Root directory
│   BlockchainNode.py
|   transaction_validator.py
|   network.py
│   node-list.txt
│   readme.md
```

### How It works?

The program is a minimalistic representation of a node participating in formal blockchain system, where the number of transactions are limited to ease the complexity of implementation. Each running program instance has its unique address and port number assigned to take part in a local / private peer-to-peer network where it

-   receives transactions from clients,
-   notify of other nodes that the transaction happened,
-   and reach consensus on which among the proposed proposals to encapsulate in a block and add to the global chain.

When a node is started, it first sets itself up to take the role of a server by binding to a specific IPv4 address and port number and start listening to connection requests on a separate thread. It expects connections from both clients and peer nodes. The program treats connections differently depending whom the connection is coming from. Because the IP addresses and port numbers of peer nodes are known to the program via the node-list.txt config file, it's able to distinguish between peer and client connections. Also note that while we have used blocking socket to handle all socket operations throughout the code including accepting connections, we've ensured that such operations are handled in separate threads or given a timeout constraint whenever necesary to facilitate the fluidness of network despite unexpected circumstances like failue of nodes.

Apart from our first separate thread continously accepting connections (most likely from clients after the initial setup), we also assign separate thread per accepted connection, in which it concurrently listens for any incoming data from the connection. if the received data is empty or an unexpected exception occurs, the connection is gracefully closed and the thread is cleaned. If the received data is out-of-format or contains unrecognised commands, it's also gracefully ignored.

However, when a correctly-formatted transaction request is passed on from a client, the node further verifies the content of the transaction such as the encoding used in the mesasge, value of nonce, and truthness of the digital signature. Afterwards, it notifies of the client on whether the transaction was successfully verified. if it was, it would also incur the "conensus rounds", by sending off block requests to all of its connected peers. When other nodes receive the block reqeust for the first time for a particular block, they also start the "consensus rounds". What it does is essntially repeating the process of sending off block request and pocessing the responses from other nodes for ceil(n / 2) - 1 rounds, where n represents the total number of nodes participating in the network (inlucding itself).

It is critical to note that the connection used to send and receive block requests is different. Receiving a block request and responding with your own proposals is handled in the same thread as receiving transactions. The thread simply responds to any valid requests submitted in the proper format, including block requests.

However, sending a block request is a bit different. We create and reuse a new connection from the node to its peer instead of the accepted connection. This is primarily due to industry standards that require separate connections for reading and writing data. This approach is especially useful for adhering to the assignment's specifications because we can apply timeout constraints to sending block requests and waiting for proposals, without having to worry about it interfering with the read operations if it were to share the same connection. For instance, if a node were to be reading a long message from its peer and also waiting for the response to its blocck request in parallel using the same connection, the timeout may cause the connection to break while reading, making the system lose data frequently, leading to low reliability.

Finally, after a set of "consensus rounds" is complete, the nodes must decide on the transaction to append to its blockchain. This is quite the trivial process because our blockchain simply wants to store the transaction with least lexographical hash value; what makes it even more trivial is the assumption of the A3 specification that there exists only one unique transaction per "consensus rounds". We do want to emphasize that our implementation has stepped a little further to imitate the real-world blockchain systems, where there are many transcation per block to be encapsulated, and is able to deal with multiple tranaction sent from multiple clients in a very short time interval.

As a one final sidenote / reflection, we've noticed that our implementation does not discriminate between requests sent from clietns and peer nodes. What this means is that as long as the request is in the correct format, the node willingly rsponds to the request with whatever information it has available without much doubt. We think that this could potentially be a security flaw, where uncertified computers may also act like they're the nodes participating in the network and interfere with the consensus algorithm. We are willing to investigate further into the implications of this and fixing the code in the near future.

### How to run?

-   #### COMP3221_BlockchainNode.py

It requires `two` command-line arguments: **port number** and **a list of nodes in txt format**.

```
python3 COMP3221_BlockchainNode.py <port-number> <node-list.txt>
```

Usage Example

```
python3 BlockchainNode.py 8888 node-list.txt
```

To simulate the entire network on a single machine, run a programme for each node in the node-list.txt with the appropriate IP addresses and port numbers. To simulate the network in a private network, please make an effort to change the binding IP address in the main source file to your private IPv4 address and correctly write other peers' private IPv4 addresses and port numbers into the node-list.txt.
