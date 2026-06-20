import { Client, Collection, Events, GatewayIntentBits, REST, Routes, MessageFlags } from 'discord.js';
import * as fs from 'fs';
import * as path from 'path';
import { pathToFileURL } from 'url';
import 'dotenv/config';
import { calcTransactionCost, estimateGas, initCrypto, watchMMWalletTrans } from './utils/crypto';
import prisma from './db';
import { handleTradeInvite } from './btnHandlers/invite';
import { setup } from './msgHandlers/setup';
import { configCache } from './storage';
import * as cfgService from "./services/config"
import { Config } from './generated/prisma/browser';
const express = require("express")
const app = express()

class MyClient extends Client {
    commands = new Collection<string, any>();
}

const client = new MyClient({
    intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

async function deployCommands(myClient: MyClient) {
    if (!process.env.DIS_BOT_TOKEN || !process.env.CLIENT_ID) {
        return console.error('[ERROR] Отсутствуют токены в .env (DIS_BOT_TOKEN или CLIENT_ID)');
    }

    const rest = new REST().setToken(process.env.DIS_BOT_TOKEN);

    try {
        const commandsData = myClient.commands.map(cmd => cmd.data.toJSON());

        console.log(`[DEPLOY] Начинаю обновление ${commandsData.length} команд...`);

        // Глобальное обновление (может занять время, для тестов на одном сервере используй applicationGuildCommands)
        await rest.put(
            Routes.applicationCommands(process.env.CLIENT_ID),
            { body: commandsData },
        );

        console.log('[DEPLOY] Команды успешно синхронизированы!');
    } catch (error) {
        console.error('[ERROR] Ошибка деплоя:', error);
    }
}

watchMMWalletTrans()
console.log("NET ", process.env.mainnet === "false")

async function init() {

    // console.log("CRYPTO " net)
    const commandsPath = path.join(process.cwd(), 'src-ts', 'commands');

    if (!fs.existsSync(commandsPath)) {
        console.error(`[ERROR] Папка с командами не найдена: ${commandsPath}`);
        return;
    }

    const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.ts') || file.endsWith('.js'));

    for (const file of commandFiles) {
        const filePath = path.join(commandsPath, file);
        const fileUrl = pathToFileURL(filePath).href;

        try {
            const command = await import(fileUrl);
            const cmd = command.default || command;

            if (cmd.data && cmd.execute) {
                client.commands.set(cmd.data.name, cmd);
                console.log(`[INFO] Команда /${cmd.data.name} загружена.`);
            }
        } catch (err) {
            console.error(`[ERROR] Не удалось загрузить ${file}:`, err);
        }
    }

    await client.login(process.env.DIS_BOT_TOKEN);
        new Promise(async (res) => {
        // const cfg = await prisma.config.findFirst()
        // console.log(cfg, !cfg)
        // if(cfg === null) {
        //     await prisma.config.create({data:{embed_suc_color:"0xff1a18"}})
        //     console.log("created")
        //     return res
        // }
    })

}

let initedCrypto = false
client.on("interactionCreate", async (interaction: any) => {
  if (!initedCrypto) {
    await initCrypto(interaction.guildId)
    initedCrypto = true
  }
  handleTradeInvite(interaction)
  console.log("Pressed", interaction.user.username)
})

client.on("messageCreate", async (msg) => {
  if (msg.author.bot || !msg.content?.startsWith("-"))
    return
  await setup(msg)
})

client.once(Events.ClientReady, async (readyClient) => {
    console.log(`✅ Ready! Logged in as ${readyClient.user.tag}`);

    await deployCommands(client);
    console.log(`[SYSTEM] Бот полностью готов к работе.`);
});

function checkCfg(cfg: Config) {
  const res = []
  if (cfg.mmWallet === null)
    res.push("mmWallet")
  if (cfg.publicLogChanId === null)
    res.push("publocLogChanId")
  if (cfg.privateLogChanId === null)
    res.push("privateLogChanId")
  if (cfg.supportRequestChanId === null)
    res.push("supportRequestChanId")
  return res
}

client.on(Events.InteractionCreate, async (interaction) => {
    if (!initedCrypto) {
      await initCrypto(interaction.guildId || "")
      initedCrypto = true
    }
    if (!interaction.isChatInputCommand()) return;

    const command = client.commands.get(interaction.commandName);
    if (!command) return;

  try {
    const cfg = await cfgService.get(interaction.guildId || "")
    const res = checkCfg(cfg)
      if (res.length > 0)
          return await interaction.reply({content:"Error: Config is not set " +res.join(" "), flags:MessageFlags.Ephemeral})
      await command.execute(interaction);
    } catch (error) {
        console.error(error);
        const reply = { content: 'Error Happenned', ephemeral:true };
        if (interaction.replied || interaction.deferred) await interaction.followUp(reply);
        else await interaction.reply(reply);
    }
});
process.on('unhandledRejection', (reason, promise) => {
    console.error('КРИТИЧЕСКАЯ ОШИБКА (Unhandled Rejection):');
    console.error(reason);

});

process.on('uncaughtException', (error) => {
    console.error('❌ КРИТИЧЕСКАЯ ОШИБКА (Uncaught Exception):');
    console.error(error);
});

init();

app.get("/users/:id", async (req: any,res: any) => {
    const user = await prisma.user.findFirst({where:{discordId:req.params.id}, include:{sentTrades:true, receivedTrades:true}})
    res.json(user)
})

app.get("/trades/:id", async (req: any, res: any) => {
    const trade = await prisma.trade.findFirst({where:{id:parseInt(req.params.id)}, include:{sender:true, reciever:true}})
    res.json(trade)
})

app.listen(3000, async () => {
  console.log("express is running")
  console.log(await calcTransactionCost("0x377BcD30C0fa6C86136eD0772Dc251A265C1C6DF", "0.0649"))
})
