import prisma from "../db";
import { Config } from "../generated/prisma/browser";
import { configCache } from "../storage";


export async function get(guildId: string): Promise<Config> {
  const cacheCfg = configCache.get(guildId)
  if (cacheCfg === undefined) {
    const cfg: any = await prisma.config.findFirst({ where: { guildId: guildId || "" } })

    configCache.set(guildId, cfg)
    return cfg
  }
  return cacheCfg
}

export async function update(guildId: string, data: any) {
  const cfg = await prisma.config.update({ data: data, where: { guildId: guildId } })
  configCache.set(guildId, cfg)
  return cfg
}

export async function init(guildId: string) {

}
