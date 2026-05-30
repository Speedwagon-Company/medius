import { createPublicClient, webSocket, Hex, PublicClient, http, HttpTransport, RpcSchema, createWalletClient, Transaction } from 'viem';
import { mainnet, sepolia } from 'viem/chains';
import { HttpRpcClient, parseEther } from 'viem/utils';
import { sleep } from './index';
import { privateKeyToAccount } from 'viem/accounts';
// transport:http(process.env.RPC_URL),
export const ethHttp = createPublicClient({
    chain: sepolia,
    transport: http(process.env.RPC_URL, {
        timeout: 60000, 
        retryCount: 3,
        retryDelay: 1000,
    }),
});
const MM_ADDRESS = process.env.OWNER_WALLET || ""
const mmAcc = privateKeyToAccount(`0x${process.env.PRIVATE_WALLET_KEY}`)
const mmAccClient = createWalletClient({
    account:mmAcc,
    chain: mainnet,
    transport: http(process.env.RPC_URL)
  })
const transactions: Map<string, any> = new Map()


export function watchMMWalletTrans() {
  const client = ethHttp
  const unwatch = client.watchBlocks({
  onBlock: async (block) => {
    console.log(`Новый блок: ${block.number}`)

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
    myTxs.forEach((tx: any) => {
      transactions.set(tx.from, tx)
      console.log("set trans: ", transactions, tx.from)
    })
  },
  pollingInterval: 10_000, 
})
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