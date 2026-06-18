import { ButtonInteraction, CacheType, Interaction } from "discord.js";
import EventEmitter from "node:events";
import * as inviteService from "../services/invite"

export async function handleTradeInvite(inter: ButtonInteraction) {
  if (inter.customId === undefined)
    return

  const id = inter.customId.split("_")
  if (id[0] !== "trade" || id[1] !== "invite")
    return
  const inviteId = id[2]
  console.log("Passed", id, id[4] === "declince", id[3])
  const btnData: InviteTradeBtnRes = { accepted: true, userId: inter.user.id }
  if (id[3] === "declince") {
    btnData.accepted = false
    await inviteService.declince(Number(inviteId))
  } else if (id[3] == "accept") {
    await inviteService.accept(Number(inviteId))

  }

  await inter.reply({content:"Success"})
  console.log(inviteId,btnData)
  tradeEventEmitter.resolveResponse(inviteId, btnData)



}

class TradeEventEmitter extends EventEmitter {
  private waitingResponses = new Map<string, (result: InviteTradeBtnRes) => void>();

  waitForResponse(inviteId: string): Promise<InviteTradeBtnRes> {
    return new Promise((resolve) => {
      this.waitingResponses.set(inviteId, resolve);
      console.log(this.waitingResponses)
      // setTimeout(() => {
      //   if (this.waitingResponses.has(inviteId)) {
      //     this.waitingResponses.delete(inviteId);
      //     resolve({ accepted: false, error: 'timeout' });
      //   }
      // }, 60000);
    });
  }

  resolveResponse(inviteId: string, result: InviteTradeBtnRes) {
    const resolver = this.waitingResponses.get(inviteId);
    if (resolver) {
      resolver(result);
      this.waitingResponses.delete(inviteId);
    }
  }
}

export interface InviteTradeBtnRes {
  accepted: boolean;
  userId?: string;
  error?: string;
}

export const tradeEventEmitter = new TradeEventEmitter();
