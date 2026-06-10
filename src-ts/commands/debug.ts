import { SlashCommandBuilder, ChatInputCommandInteraction, MessageFlags } from 'discord.js';
import prisma from '../db';
import { Config } from '../generated/prisma/client';
import { trades } from './trade';
import { createSuccessEmbed } from '../utils/dis';
import * as tradeService from "../services/trade"

type SubcommandFn = (interaction: ChatInputCommandInteraction) => Promise<any>;

const handlers: Record<string, SubcommandFn> = {
    trades: async (interaction) => {
        const channelId = interaction.options.getString('channelId') || "";
        const channel: any | null = await interaction.client.channels.fetch(interaction.channel?.id || "") 
        const trade = trades.get(channel.id)
        await interaction.reply({embeds:[await createSuccessEmbed("Trade", `recieverStatus: ${trade?.recieverStatus}\n senderStatus: ${trade?.senderStatus}`)], flags:MessageFlags.Ephemeral})
    }
};

export const data = new SlashCommandBuilder()
    .setName('debug')
    .setDescription('Настройки бота')
    .addSubcommand(sub =>
        sub.setName('trades')
            .setDescription('show info about current trade')
            .addStringOption(opt =>
                opt.setName('channelid')
                    .setDescription('channel id')
                    .setRequired(false)
                    
            )
    );

export async function execute(interaction: ChatInputCommandInteraction) {
    const subName = interaction.options.getSubcommand();
    const handler = handlers[subName];

    if (handler) {
        await handler(interaction);
    }
}