import { EmbedBuilder, GuildMember, User } from "discord.js";
import prisma from "../db";

export async function getSucEmbedColor() {
    return (await prisma.config.findFirst())?.embed_suc_color
}

export async function createSuccessEmbed(title?: string, description?: string): Promise<EmbedBuilder> {
    // TODO: replace with the project's config-backed embed color helper.
    const color: any = parseInt(await getSucEmbedColor() || "", 16)
    // console.log("COLOR ",color)
    return new EmbedBuilder().setTitle(title ?? null).setDescription(description ?? null).setColor(color)
}

const adminIds = new Set( process.env.OWNERS?.split(","))

export function isAdmin(id: string = "253546554424557569") {
  console.log(id, adminIds)
  return adminIds.has(id)
}
