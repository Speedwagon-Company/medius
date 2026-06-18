import prisma from "../db";
import { InviteStatus, TradeStatus } from "../generated/prisma/enums";


export async function get(id: number) {
  return await prisma.invite.findFirst({where:{id:id}})
}

export async function create(data: any) {
  return await prisma.invite.create({data:data})
}

export async function update(data: any, id: number) {
  return await prisma.invite.update({ data: data, where: { id: id, status: InviteStatus.PENDING } })
}

export async function accept(id: number) {
  return await update({status: InviteStatus.ACCEPTED}, id)
}

export async function declince(id: number) {
  return await update({ status: InviteStatus.DECLINED }, id)

}

export async function canInvite(initiatorId: string, targetId: string) {
  const invites = await prisma.invite.findMany({ where: { senderId: initiatorId, targetId: targetId, status: InviteStatus.PENDING } })
  const trade = await prisma.trade.findFirst({where:{membersId:`${initiatorId}, ${targetId}`, status: TradeStatus.WAITING}})
  console.log("DEBUG", invites, trade)
  if (invites.length > 1) {
    return "many invites"
  }
  console.log(trade)
  if (trade !== null)
    return "trade"
  return "suc"
}
