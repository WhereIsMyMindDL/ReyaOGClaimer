import time
import asyncio
import aiohttp
import pandas as pd
from sys import stderr
from loguru import logger
from eth_account.account import Account
from eth_account.messages import encode_typed_data, encode_defunct

logger.remove()
logger.add(stderr,
           format="<lm>{time:HH:mm:ss}</lm> | <level>{level}</level> | <blue>{function}:{line}</blue> "
                  "| <lw>{message}</lw>")


def async_error_handler(error_msg, retries=3):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for i in range(0, retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # logger.error(f"{error_msg}: {str(e)}")
                    if i == retries - 1:
                        return 0
                    await asyncio.sleep(2)

        return wrapper

    return decorator


class ReyaOGClaimer:
    def __init__(self, private_key: str, proxy: str, number_acc: int) -> None:
        self.private_key = private_key
        self.account = Account().from_key(private_key=private_key)
        self.proxy: str = f"http://{proxy}" if proxy is not None else None
        self.id: int = number_acc
        self.client = None

    async def create_message(self) -> str and int:
        deadline: int = int(time.time() + 600000)

        message = {
            "types": {
                "MintBySig": [
                    {
                        "name": "verifyingChainId",
                        "type": "uint256"
                    },
                    {
                        "name": "owner",
                        "type": "address"
                    },
                    {
                        "name": "leafInfo",
                        "type": "LeafInfo"
                    },
                    {
                        "name": "merkleRoot",
                        "type": "bytes32"
                    },
                    {
                        "name": "deadline",
                        "type": "uint256"
                    }
                ],
                "LeafInfo": [
                    {
                        "name": "owner",
                        "type": "address"
                    },
                    {
                        "name": "tokenRootCount",
                        "type": "uint256"
                    }
                ],
                "EIP712Domain": [
                    {
                        "name": "name",
                        "type": "string"
                    },
                    {
                        "name": "version",
                        "type": "string"
                    },
                    {
                        "name": "verifyingContract",
                        "type": "address"
                    }
                ]
            },
            "domain": {
                "name": "Reya",
                "version": "1",
                "verifyingContract": "0x14d7c1efc024e118df70b241afbd2447d37f1ed6"
            },
            "primaryType": "MintBySig",
            "message": {
                "verifyingChainId": "1729",
                "owner": self.account.address,
                "leafInfo": {
                    "owner": self.account.address,
                    "tokenRootCount": "0"
                },
                "merkleRoot": "0xbc6264e25255e1b3d456ec287615879c2525828345a3d4d4c09eb11baa2d201f",
                "deadline": deadline
            }
        }

        signature = Account.sign_message(encode_typed_data(full_message=message), self.private_key).signature.hex()
        return signature, deadline

    async def activate_account(self):
        response: aiohttp.ClientResponse = await self.client.get(
            f'https://api.reya.xyz/api/accounts/{self.account.address}',
            proxy=self.proxy,
        )
        response_json: dict = await response.json()

        if len(response_json) == 0:
            logger.info(f'#{self.id} | {self.account.address} account is not activated')

            msg = encode_defunct(text=f'Reya Labs Limited Terms and Conditions: '
                                      f'https://reya.xyz/files/ReyaLabsLimited_Reya_xyz_T&Cs_04April2024.pdf')
            text_signature = self.account.sign_message(msg)

            response: aiohttp.ClientResponse = await self.client.post(
                f'https://api.reya.xyz/api/owner/tos/add-signature',
                json={
                    'signature': f'0x{text_signature.signature.hex()}',
                    'walletAddress': self.account.address,
                    'message': 'Reya Labs Limited Terms and Conditions: '
                               'https://reya.xyz/files/ReyaLabsLimited_Reya_xyz_T&Cs_04April2024.pdf',
                    'version': '4',
                },
                proxy=self.proxy,
            )

            response: aiohttp.ClientResponse = await self.client.post(
                f'https://api.reya.xyz/api/transaction-gelato/executeGelato',
                json={
                    'txData': {
                        'to': '0xa763b6a5e09378434406c003dae6487fbbdc1a80',
                        'data': f'0x9859387b000000000000000000000000{self.account.address[2:]}',
                    },
                    'contractAddress': '0xa763b6a5e09378434406c003dae6487fbbdc1a80',
                    'metadata': {
                        'accountName': 'Margin Account 1',
                        'action': 'createAccount',
                        'sender': self.account.address,
                    },
                },
                proxy=self.proxy,
            )
            response_json: dict = await response.json()

            if 'txHash' in response_json:
                logger.success(f'#{self.id} | {self.account.address} account activated')

    @async_error_handler('check_eligible')
    async def check_eligible(self) -> None:
        async with aiohttp.ClientSession(headers={
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Connection': 'keep-alive',
            'Origin': 'https://app.reya.network',
            'Referer': 'https://app.reya.network/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/126.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }) as client:
            self.client = client

            await ReyaOGClaimer.activate_account(self)

            response: aiohttp.ClientResponse = await self.client.get(
                f'https://api.reya.xyz/api/sbt/mint-status/owner/{self.account.address}/tokenCount/0',
                proxy=self.proxy,
            )
            response_json: dict = await response.json()
            if response_json['isEligible'] and not response_json['hasMinted']:
                logger.info(f'#{self.id} | {self.account.address} eligible')

                signature, deadline = await ReyaOGClaimer.create_message(self)

                response: aiohttp.ClientResponse = await self.client.put(
                    f'https://api.reya.xyz/api/sbt/mint',
                    json={
                        'owner': self.account.address,
                        'merkleRoot': '0xbc6264e25255e1b3d456ec287615879c2525828345a3d4d4c09eb11baa2d201f',
                        'tokenRootCounter': 0,
                        'signature': f'0x{signature}',
                        'signatureDeadline': deadline,
                    },
                    proxy=self.proxy,
                )
                response_json: dict = await response.json()

                if 'txHash' in response_json:
                    logger.success(f'#{self.id} | {self.account.address} success minted')

                else:
                    logger.info(f'#{self.id} | {self.account.address} not minted')

            elif response_json['isEligible'] and response_json['hasMinted']:
                logger.info(f'#{self.id} | {self.account.address} already minted')

            elif not response_json['isEligible']:
                logger.info(f'#{self.id} | {self.account.address} not eligible')


async def start_work(account: list, id_acc: int, semaphore) -> None:
    async with semaphore:
        acc = ReyaOGClaimer(private_key=account[0], proxy=account[1],
                            number_acc=id_acc)

        try:

            await acc.check_eligible()

        except Exception as e:
            logger.error(f'ID account:{id_acc} Failed: {str(e)}')


async def main() -> None:
    semaphore: asyncio.Semaphore = asyncio.Semaphore(1)  # колличество потоков

    tasks: list[asyncio.Task] = [
        asyncio.create_task(coro=start_work(account=account, id_acc=idx, semaphore=semaphore))
        for idx, account in enumerate(accounts, start=1)
    ]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    with open('accounts_data.xlsx', 'rb') as file:
        exel = pd.read_excel(file)
    accounts: list[list] = [
        [
            row["Private key"],
            row["Proxy"] if isinstance(row["Proxy"], str) else None
        ]
        for index, row in exel.iterrows()
    ]
    logger.info(f'My channel: https://t.me/CryptoMindYep')
    logger.info(f'Total wallets: {len(accounts)}\n')

    asyncio.run(main())

    logger.success('The work completed')
    logger.info('Thx for donat: 0x5AfFeb5fcD283816ab4e926F380F9D0CBBA04d0e')
