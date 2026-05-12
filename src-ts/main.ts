import "reflect-metadata";
import "dotenv/config";

import { Events, GatewayIntentBits } from "discord.js";
import { CogsClient } from "discord.ts-cogs";
import { TradeCog } from "./cogs/trade";
import { ethHttp, waitForTransaction, watchMMWalletTrans, signAndSend } from "./utils/crypto";
import { Hex } from "viem";


const token = process.env.DIS_BOT_TOKEN ?? process.env.DISCORD_BOT_TOKEN;
const configuredClientId = process.env.DISCORD_CLIENT_ID;
const guildId = process.env.DISCORD_GUILD_ID;
const wsUrl = process.env.CHAINSTACK_WS || ""

if (!token) {
  throw new Error("DIS_BOT_TOKEN or DISCORD_BOT_TOKEN must be set.");
}

const client = new CogsClient({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});
console.log(ethHttp)

// watchPendingTransactions(wsUrl, (txHash: Hex, blockNumber?: bigint) => {
//   console.log(txHash, blockNumber)
// }, 
// (err) => console.log(err))
watchMMWalletTrans();
// (async () => {
//   await signAndSend(0.001, "0x377BcD30C0fa6C86136eD0772Dc251A265C1C6DF")
//   console.log("sent")
// })()
client.addCog(new TradeCog());

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) {
    return;
  }

  const command = client.commands.get(interaction.commandName);
  if (!command) {
    return;
  }

  try {
    await command.call(interaction);
  } catch (error) {
    console.error(`Command ${interaction.commandName} failed`, error);

    const payload = {
      content: "Command failed unexpectedly. Check logs for details.",
      ephemeral: true,
    };

    if (interaction.deferred || interaction.replied) {
      await interaction.followUp(payload).catch(() => undefined);
    } else {
      await interaction.reply(payload).catch(() => undefined);
    }
  }
});

client.once(Events.ClientReady, async (readyClient) => {
  console.log(`Ready! Logged in as ${readyClient.user.tag}`);

  const clientId = configuredClientId ?? readyClient.user.id;
  await client.syncCommands(token, clientId, guildId);

  const scope = guildId ? `guild ${guildId}` : "global";
  console.log(`Synced ${client.commands.size} slash command(s) to ${scope}.`);
});

void client.login(token);
