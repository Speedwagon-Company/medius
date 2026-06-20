import {
  EmbedBuilder,
  Guild,
  Message,
  MessageFlags,
  MessageFlagsBitField,
} from "discord.js";
import { configCache } from "../storage";
import { Config } from "../generated/prisma/browser";
import { createSuccessEmbed, isAdmin } from "../utils/dis";
import { InvalidCmdException } from "../exceptions/InvalidCommand";
import prisma from "../db";
import * as cfgService from "../services/config";

const admRoleIds = process.env.OWNERS?.split(",");
const commads = new Set(["-set", "-help"]);
const subCmds = new Set([
  "publicLogChanId",
  "privateLogChanId",
  "init",
  "mmWallet",
  "supportRequestChanId"
]);
const prefix = "-";

export async function setup(msg: Message<boolean>) {
  if (!isAdmin(msg.author.id)) {
    console.log(isAdmin(msg.author.id));
    const id = await msg.guild?.members.fetch(msg.author.id);
    console.log(id?.id, typeof id?.id);
    await msg.reply({
      content: "You are not admin",
    });
    return;
  }
  try {
    const status = await handleSubCmds(msg);
    if (status === "dont")
      return
    await msg.reply({
      content: "Success",
    });
  } catch (e: any) {
    console.log(e);
    if (e.message === "Channel not found")
      await msg.reply({ content: "Channel not found" });
  }
}

async function handleHelp(msg: Message) {
  const embed = new EmbedBuilder()
    .setTitle("Commands help")
    .addFields({
      name: "-set publicLogChannelId IDHERE",
      value: "sets public log channel for trades",
    },
    {name:"-set privateLogChanId IDHERE",value:"sets private log channel for trades"});
  await msg.reply({ embeds: [embed] });
}

async function handleSubCmds(msg: Message) {
  const cmd = msg.content.split(" ");
  const subCmd = cmd[1];
  console.log();
  if (cmd[0] === "-help") {
    await handleHelp(msg);
    return "dont"
  }
  const id = msg.guildId || "";
  if (cmd[0] === "-init") {
    await prisma.config.create({
      data: { guildId: id || "", embed_suc_color: "0xff1a18" },
    });
    return "dont"
  }
  if (!commads.has(`${cmd[0]}`) || !subCmds.has(subCmd)){
    throw new InvalidCmdException("");
  }

  console.log(id, cmd[2]);

  const guild = msg.guild;
  if (subCmd === "publicLogChanId") {
    const chan = await getChan(guild, cmd[2]);
    if (chan === null) throw new Error("Channel not found");
    const cfg = await cfgService.update(id, { publicLogChanId: cmd[2] });
  } else if (subCmd === "privateLogChanId") {
    const chan = await getChan(guild, cmd[2]);
    if (chan === null) throw new Error("Channel not found");
    const cfg = await cfgService.update(id, { privateLogChanId: cmd[2] });
  } else if (subCmd === "mmWallet") {
    await cfgService.update(id, { mmWallet: cmd[2] });
  } else if (subCmd === "supportRequestChanId") {
    const chan = await getChan(guild, cmd[2]);
    if (chan === null) throw new Error("Channel not found");
    const cfg = await cfgService.update(id, { supportRequestChanId: cmd[2] });
  }
}

async function getChan(guild: Guild | null, id: string) {
  if (guild === null) return null;
  try {
    return await guild.channels.fetch(id);
  } catch (e) {
    return null;
  }
}
