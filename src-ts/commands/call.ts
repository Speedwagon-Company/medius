import { SlashCommandBuilder, ChatInputCommandInteraction, Channel, MessageFlags, ButtonBuilder, ActionRowBuilder, ButtonStyle, ComponentType, ButtonInteraction, ThreadChannel, Message } from 'discord.js';
import prisma from '../db';
import { Config } from '../generated/prisma/client';
import { randomUUID, UUID } from 'node:crypto';
import { createSuccessEmbed } from '../utils/dis';
import { trades } from './trade';

type SubcommandFn = (interaction: ChatInputCommandInteraction) => Promise<any>;
const SUP_REQ_CHAN_ID = "1505282213577490553"

const handlers: Record<string, SubcommandFn> = {
    support: async (interaction) => {
        const channel: any | null = await interaction.client.channels.fetch(interaction.channel?.id || "") 
        if(!channel.name) {
            return
        }
        
        if(channel.name.split("-")[0] !== "trade") {
            return await interaction.reply({content:"You are not in trade room", flags:MessageFlags.Ephemeral})
        }
        const trade = trades.get(channel.id)
        if(!trade?.canCallSupport) {
            return await interaction.reply({content:"You cant call support",flags:MessageFlags.Ephemeral}, )
        }


        let reason = interaction.options.getString("reason")
        if(reason == null) {
            reason = "Not given"
        }
        const id = randomUUID()
        const supportReqChan: any = await interaction.client.channels.fetch(SUP_REQ_CHAN_ID) 
        const row =  buildReqSupportBtn(id)
        const embed = await createSuccessEmbed(`Support request`, `User ${interaction.user.username} requested support \nReason: ${reason}`)
        const message: Message = await supportReqChan.send({ embeds:[embed],components:[row]})
        await interaction.reply({content:`<@${interaction.user.id}> called support`})
        return new Promise((res,rej) => {
            const collector = message.createMessageComponentCollector({
                componentType: ComponentType.Button,
                time: 0, 
            });
            collector.on("collect", async (button: ButtonInteraction) => { 
                if(button.customId === id) {
                    if(channel.members.cache.has(interaction.member?.user.id)){
                        return await interaction.reply({content:"You already in this channel",flags:MessageFlags.Ephemeral}, )
                    }
                    // row.components.forEach((v: ButtonBuilder) => v.setDisabled(true))
                    await channel.members.add(interaction.user)
                    message.edit({embeds:[embed]})
                    await channel.send(`Added <@${button.user.id}>`)
                }
            })
        })
    }
};

function buildReqSupportBtn(
    msgId: string
): ActionRowBuilder<ButtonBuilder> {
    return new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
            .setCustomId(msgId)
            .setLabel("Respond")
            .setStyle(ButtonStyle.Success),
            // .setDisabled(Boolean(roles[TradeRole.Receiver])),

    );
}

export const data = new SlashCommandBuilder()
    .setName('call')
    .setDescription('Настройки бота')
    .addSubcommand(sub =>
        sub.setName('support')
            .setDescription('call support')
            .addStringOption(opt =>
                opt.setName('reason')
                    .setDescription('write a reason')
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