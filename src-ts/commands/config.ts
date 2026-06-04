import { SlashCommandBuilder, ChatInputCommandInteraction } from 'discord.js';
import prisma from '../db';
import { Config } from '../generated/prisma/client';

type SubcommandFn = (interaction: ChatInputCommandInteraction) => Promise<any>;

const handlers: Record<string, SubcommandFn> = {
    color: async (interaction) => {
        const color = interaction.options.getString('value') || "";
        const cfg: Config | null = await prisma.config.findFirst()
        if(!cfg) {
            return
        }

        await prisma.config.update({where:{id: cfg.id},data:{embed_suc_color:color}})
        await interaction.reply({ content: `🎨 Цвет конфигурации изменен на: **${color}**`, ephemeral: true });
    }
};

export const data = new SlashCommandBuilder()
    .setName('config')
    .setDescription('Настройки бота')
    .addSubcommand(sub =>
        sub.setName('color')
            .setDescription('Изменить цвет интерфейса')
            .addStringOption(opt =>
                opt.setName('value')
                    .setDescription('Выберите цвет')
                    .setRequired(true)
                    
            )
    
    )
    .addSubcommand(sub =>
        sub.setName("init")
        .setDescription("init config")
    );

export async function execute(interaction: ChatInputCommandInteraction) {
    const subName = interaction.options.getSubcommand();
    const handler = handlers[subName];

    if (handler) {
        await handler(interaction);
    }
}