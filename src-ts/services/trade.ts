import prisma from "../db";


export async function create(tradeData: any) {
  return await prisma.trade.create({ data: tradeData })
}

export async function update(tradeData: any, channelId: string) {
    return await prisma.trade.update({data:tradeData, where:{channelId:channelId}})
}

export async function get(id: string) {
    return await prisma.trade.findFirst({where:{channelId:id}, include:{sender:true, reciever:true}})
}
