import { createPublicClient, webSocket, Hex, PublicClient, http, HttpTransport, RpcSchema, createWalletClient, Transaction } from 'viem';
import { mainnet, sepolia } from 'viem/chains';
import { formatEther, formatGwei, HttpRpcClient, parseEther } from 'viem/utils';
import { sleep } from './index';
import { privateKeyToAccount } from 'viem/accounts';
import * as cfgService from "../services/config"
import { exit } from 'node:process';
import * as tradeService from "../services/trade"
import prisma from '../db';
import { TradeStatus } from '../generated/prisma/enums';
// transport:http(process.env.RPC_URL),
//

const rpcUrl = process.env.mainnet === "true" ? process.env.MAINNET_RPC : process.env.RPC_URL
const wsUrl = process.env.mainnet === "true" ? process.env.MAINNET_WS : process.env.CHAINSTACK_WS
const net  =process.env.mainnet === "true" ? mainnet : sepolia

export const ethHttp = createPublicClient({
    chain: net,
    transport: http(rpcUrl, {
        timeout: 60000,
        retryCount: 3,
        retryDelay: 1000,
    }),
});
let MM_ADDRESS =  process.env.OWNER_WALLET || ""
const mmAcc = privateKeyToAccount(`0x${process.env.PRIVATE_WALLET_KEY}`)
const mmAccClient = createWalletClient({
    account:mmAcc,
    chain: mainnet,
    transport: http(process.env.RPC_URL)
  })
const transactions: Map<string, any> = new Map()

export async function initCrypto(id: string) {
  const cfg = await cfgService.get(id)
  console.log("CFG", cfg)
  if (cfg === null)
    exit(1)
  console.log("CRYPTO ", cfg.mmWallet, net)
  if (cfg.guildId === "")
    throw Error("Crypto mm")
  // MM_ADDRESS = cfg.guildId || ""
}

export function watchMMWalletTrans() {
  const client = ethHttp
  const unwatch = client.watchBlocks({
  onBlock: async (block) => {
    // console.log(`Новый блок: ${block.number} ${MM_ADDRESS}`)
    const blockWithTxs = await client.getBlock({
      blockNumber: block.number,
      includeTransactions: true
    })

    const myTxs: any = blockWithTxs.transactions.filter(
      (tx) =>
        tx.from?.toLowerCase() === MM_ADDRESS.toLowerCase() ||
        tx.to?.toLowerCase() === MM_ADDRESS.toLowerCase()
    )

    // if (myTxs.length > 0) {
    //   console.log('Найдены новые транзакции:', myTxs)
    // }
      myTxs.forEach(async (tx: any) => {
        console.log("FINDING ", tx.from)
        const trade =await prisma.trade.findFirst({where:{senderWallet:tx.from.toLowerCase(), status:TradeStatus.WAITING}})
        console.log("TRYING TO SET TRANS", trade?.id)
        if (trade !== null) {
          transactions.set(tx.from, tx)
          console.log("set trans: ", transactions, tx.from)

        }
    })
  },
  pollingInterval: 10_000,
})
}

export function calculateFee(
  amountEth: string,
  ethPriceInUSD: number
): number {
  const amountInEth = Number(amountEth);
  const amountInUSD = amountInEth * ethPriceInUSD;

  let feeInUSD: number;

  if (amountInUSD > 250) {
    feeInUSD = (amountInUSD * 0.01);
  } else if (amountInUSD >= 50 && amountInUSD <= 249) {
    feeInUSD = 2;
  } else {
    feeInUSD = 0;
  }

  // Переводим комиссию обратно в ETH
  const feeInEth = feeInUSD / ethPriceInUSD;

  return feeInEth;
}


export async function waitForTransaction(wallet: string): Promise<Transaction> {
  while(true) {
    const trans = transactions.get(wallet.toLowerCase())
    if(trans){
      transactions.delete(wallet.toLowerCase())
      return trans
    }
    await sleep(1000)
  }
}

export async function signAndSend(amount: number, to: string) {
  console.log('start sign', amount, to, typeof to)

  console.log('ACC', mmAcc.address)

  const hash = await mmAccClient.sendTransaction({
    to: to as `0x${string}`,
    value: parseEther(amount.toString()),
  })

  console.log('SENDING', hash)

  // const receipt = await client.waitForTransactionReceipt({ hash })
  // console.log('Confirmed in block:', receipt.blockNumber)

  return hash
}

export async function estimateGas(to: string, valueWei: string): Promise<bigint> {
  try {
    const gasLimit = await ethHttp.estimateGas({
      account: mmAcc,
      to: to as `0x${string}`,
      value: parseEther(valueWei)
    });

    return gasLimit;
  } catch (e) {
    console.log(e)
    return 21000n;
  }
}

export async function calcTransactionCost(to: string, valueEth: string) {
  let gasLimit = null

  try {
  gasLimit = await ethHttp.estimateGas({
    account: mmAcc,
    to: to as `0x${string}`,
    value: parseEther(valueEth)
  });

  } catch (e) {
    gasLimit = 21000n
  }

  const gasPrice = await ethHttp.getGasPrice();

  const gasCostInWei = gasLimit * gasPrice;


  const gasCostInEth = formatEther(gasCostInWei);

  return gasCostInEth

}
