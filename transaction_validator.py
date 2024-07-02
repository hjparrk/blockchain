import re
import json
from cryptography.exceptions import InvalidSignature
import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519


def transaction_bytes(tx: dict) -> bytes:
    tx_bytes = json.dumps({k: tx.get(k) for k in [
        'sender', 'message', 'nonce']}, sort_keys=True).encode('utf-8')
    return tx_bytes


def validate_sender(payload):
    sender_valid = re.compile('^[a-fA-F0-9]{64}$')

    if not payload.get('sender'):
        return False

    if not isinstance(payload['sender'], str):
        return False

    if not sender_valid.search(payload['sender']):
        return False

    return True


def validate_message(payload):
    if not payload.get('message'):
        return False

    if not isinstance(payload['message'], str):
        return False

    if not len(payload['message']) <= 70:
        return False

    if not payload['message'].isalnum():
        return False

    return True


def validate_nonce(payload, nonces: dict):
    if payload.get('nonce') is None:
        return False

    if payload['nonce'] < 0:
        return False

    if payload['nonce'] <= nonces[payload['sender']]:
        return False

    nonces[payload['sender']] = payload['nonce']

    return True


def validate_signature(payload):
    signature_valid = re.compile('^[a-fA-F0-9]{128}$')

    if not payload.get('signature'):
        return False

    if not isinstance(payload["signature"], str):
        return False

    if not signature_valid.search(payload["signature"]):
        return False

    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(payload["sender"]))

        public_key.verify(bytes.fromhex(
            payload["signature"]), transaction_bytes(payload))
    except InvalidSignature:
        return False

    return True


def validate_transaction(tx, addr, nonces: dict):

    if not tx.get('payload'):
        return False

    payload = tx['payload']
    print(f"[NET] Received a transaction from node {addr[0]}: {payload}\n")

    if not validate_sender(payload):
        print(
            f"[TX] Received an invalid transaction, wrong sender - {payload}\n")
        return False

    if not validate_message(payload):
        print(
            f"[TX] Received an invalid transaction, wrong message - {payload}\n")
        return False

    if not validate_nonce(payload, nonces):
        print(
            f"[TX] Received an invalid transaction, wrong nonce - {payload}\n")
        return False

    if not validate_signature(payload):
        print(
            f"[TX] Received an invalid transaction, wrong signature message - {payload}\n")
        return False

    return True
