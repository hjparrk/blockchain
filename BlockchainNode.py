import sys
import time
import math
import json
import socket
import hashlib
import threading
from collections import defaultdict
from network import send_prefixed, recv_prefixed
from transaction_validator import validate_transaction
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class Node:
    def __init__(self):
        self.HOST = "127.0.0.1"
        self.PORT = int(sys.argv[1])

        self.neighbours = self.get_neighbours(sys.argv[2])
        self.out_sockets = {}

        self.in_routine = False

        self.nonces = defaultdict(lambda: -1)

        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()

        self.mempool = []
        self.proposals = []
        self.blockchain = [
            {
                "index": 0,
                "transactions": [],
                "previous_hash": "0" * 64,
                "current_hash": "03525042c7132a2ec3db14b7aa1db816e61f1311199ae2a31f3ad1c4312047d1"
            }
        ]

    def get_neighbours(self, filename):
        neighbours = []
        with open(filename, 'r') as file:
            for line in file:
                host, port = line.rstrip().split(":")
                if (host == self.HOST) and (int(port) == self.PORT):
                    continue
                neighbours.append([host, int(port)])
        return neighbours

    def conn_neighbours(self):
        def conn_neighbour(host, port):
            connected = False
            while not connected:
                try:
                    out_socket = socket.socket(
                        socket.AF_INET, socket.SOCK_STREAM)
                    out_socket.connect((host, port))
                    self.out_sockets[(host, port)] = out_socket
                    print(f"Connected to {host}:{port}...")
                    connected = True
                except Exception as e:
                    time.sleep(1)

        threads = []
        for host, port in self.neighbours:
            th = threading.Thread(target=conn_neighbour, args=(host, port))
            threads.append(th)
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        print("Connected to All Neighbours")
        print("=" * 40, end="\n")

    def handle_transaction(self, client_socket, addr, tx):
        validated = validate_transaction(tx, addr, self.nonces)
        if validated:
            payload = tx['payload']
            self.mempool.append(payload)
            print(
                f"[MEM] Stored transaction in the transaction pool: {payload['signature']}\n")

            response_message = json.dumps({"response": True}).encode('utf-8')
            send_prefixed(client_socket, response_message)
            return True
        else:
            response_message = json.dumps({"response": False}).encode('utf-8')
            send_prefixed(client_socket, response_message)
            return False

    def handle_blockrequest(self, client_socket):
        proposals = self.proposals.copy()
        response = json.dumps(proposals).encode('utf-8')
        send_prefixed(client_socket, response)

    def handle_incoming_data(self, client_socket, addr):

        def calculate_hash(block: dict) -> str:
            block_object: str = json.dumps({k: block.get(
                k) for k in ['index', 'transactions', 'previous_hash']}, sort_keys=True)
            block_string = block_object.encode()
            raw_hash = hashlib.sha256(block_string)
            hex_hash = raw_hash.hexdigest()
            return hex_hash

        def create_proposal():

            last_block = self.blockchain[-1]
            index = last_block['index'] + 1
            transactions = self.mempool.copy()
            prev_hash = last_block['current_hash']

            new_proposal = {
                "index": index,
                "transactions": transactions,
                "prev_hash": prev_hash
            }
            current_hash = calculate_hash(new_proposal)
            new_proposal['current_hash'] = current_hash

            if new_proposal not in self.proposals:
                self.proposals.append(new_proposal)
                print(f"[PROPOSAL] Created a block proposal: {new_proposal}\n")

        try:
            recv_message = recv_prefixed(client_socket).decode('utf-8')
            message = json.loads(recv_message)

            allowed_types = ['transaction', 'values']
            if isinstance(message, dict) and message.get('type') and message['type'] in allowed_types:
                message_type = message['type']
            else:
                message_type = 'invalid'

            if message_type == 'transaction':
                if not self.in_routine:
                    validated = self.handle_transaction(
                        client_socket, addr, message)
                    if validated:
                        create_proposal()
                        self.in_routine = True
                else:
                    response_message = json.dumps(
                        {"response": False}).encode('utf-8')
                    send_prefixed(client_socket, response_message)

            elif message_type == 'values':

                routine_index = message['payload']
                last_block = self.blockchain[-1]

                print(
                    f"[BLOCK] Received a block request from node {addr}: {routine_index}\n")

                if routine_index <= last_block['index']:
                    response = json.dumps([last_block]).encode('utf-8')
                    send_prefixed(client_socket, response)

                else:
                    if not self.in_routine:
                        create_proposal()
                        self.handle_blockrequest(client_socket)
                        self.in_routine = True
                    else:
                        self.handle_blockrequest(client_socket)

        except Exception as e:
            print(f"[INCOMING ERROR]: {e}")

    def run_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.HOST, self.PORT))
        server_socket.listen(100)
        try:
            while True:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self.handle_incoming_data,
                                 args=(client_socket, addr)).start()
        except Exception as e:
            print(f"[SERVER ERROR]: {e}")

    def start_routine(self):

        def communicate_with_neighbour(host, port):
            address = (host, port)
            out_socket = self.out_sockets[address]

            try:
                out_socket.settimeout(5)

                last_block = self.blockchain[-1]
                last_index = last_block['index']

                br = json.dumps(
                    {"type": "values", "payload": last_index + 1}).encode('utf-8')
                send_prefixed(out_socket, br)

                recv_response = recv_prefixed(out_socket).decode('utf-8')
                response = json.loads(recv_response)

                for p in response:
                    if p not in self.proposals:
                        self.proposals.append(p)

                        if p['transactions']:
                            for tx in p['transactions']:
                                if tx['nonce'] > self.nonces[tx['sender']]:
                                    self.nonces[tx['sender']] = tx['nonce']

                out_socket.settimeout(None)

            except (socket.timeout, socket.error, RuntimeError) as e:
                # print(f"[ERROR] Communication with {address} failed: {e}")
                out_socket.close()

                try:
                    new_socket = socket.socket(
                        socket.AF_INET, socket.SOCK_STREAM)
                    new_socket.connect((host, port))
                    self.out_sockets[address] = new_socket
                    new_socket.settimeout(5)
                    send_prefixed(new_socket, br)
                    recv_response = recv_prefixed(
                        new_socket).decode('utf-8')
                    response = json.loads(recv_response)
                    for p in response:
                        if p not in self.proposals:
                            self.proposals.append(p)
                    new_socket.settimeout(None)
                except (socket.timeout, socket.error, RuntimeError) as e:
                    # print(
                    #     f"[ERROR] Communication with {address} failed after reconnect: {e}")
                    new_socket.close()
                    to_remove.append(address)

        ########### START BROADCASTING ###########
        to_remove = []

        max_failure = math.ceil((1 + len(self.neighbours)) / 2) - 1
        for _ in range(max_failure + 1):

            threads = []

            for host, port in self.neighbours:
                th = threading.Thread(
                    target=communicate_with_neighbour, args=(host, port))
                threads.append(th)

            for th in threads:
                th.start()

            for th in threads:
                th.join()

        for address in to_remove:
            print(f"Removing neighbour {address}")
            self.neighbours = [
                neighbour for neighbour in self.neighbours if tuple(neighbour) != address]
            if address in self.out_sockets:
                del self.out_sockets[address]

        ########### END BROADCASTING ###########

    def decide_block(self):
        filtered_proposals = [
            p for p in self.proposals if p.get('transactions')]
        decided_block = min(filtered_proposals,
                            key=lambda x: x['current_hash'])

        self.blockchain.append(decided_block)
        self.proposals = []
        self.mempool = []

        return decided_block['current_hash']

    def start(self):
        server_th = threading.Thread(target=self.run_server, args=())
        server_th.start()

        self.conn_neighbours()

        while True:

            if self.in_routine:
                self.start_routine()

                decided_block_hash = self.decide_block()
                print(
                    f"[CONSENSUS] Appended to the blockchain: {decided_block_hash}")

                self.in_routine = False


if __name__ == '__main__':
    node = Node()
    node.start()
