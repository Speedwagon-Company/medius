import { Client, Collection, Events, GatewayIntentBits, REST, Routes } from 'discord.js';
import * as fs from 'fs';
import * as path from 'path';
import { pathToFileURL } from 'url';
import 'dotenv/config';
import { watchMMWalletTrans } from './utils/crypto';
import prisma from './db';

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


async function init() {

    new Promise(async (res) => {
        const cfg = await prisma.config.findFirst()
        console.log(cfg, !cfg)
        if(cfg) {
            await prisma.config.create({data:{embed_suc_color:"0xff1a18"}})
            console.log("created")
            return res
        }
    })
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
}

client.once(Events.ClientReady, async (readyClient) => {
    console.log(`✅ Ready! Logged in as ${readyClient.user.tag}`);
    
    await deployCommands(client);
    console.log(`[SYSTEM] Бот полностью готов к работе.`);
});

client.on(Events.InteractionCreate, async (interaction) => {
    if (!interaction.isChatInputCommand()) return;

    const command = client.commands.get(interaction.commandName);
    if (!command) return;

    try {
        await command.execute(interaction);
    } catch (error) {
        console.error(error);
        const reply = { content: 'Произошла ошибка при выполнении команды!', ephemeral: true };
        if (interaction.replied || interaction.deferred) await interaction.followUp(reply);
        else await interaction.reply(reply);
    }
});

// Запуск
init();