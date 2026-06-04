import {
    SlashCommandBuilder, ChatInputCommandInteraction, MessageFlags,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonInteraction,
    ButtonStyle,
    ChannelType,
    ComponentType,
    EmbedBuilder,
    Guild,
    GuildMember,
    Message,
    PermissionFlagsBits,
    StringSelectMenuBuilder,
    StringSelectMenuInteraction,
    ForumThreadChannel,
    User,
    ThreadChannel,
    ForumChannel,
    GuildBasedChannel,
    ThreadAutoArchiveDuration,
    TextChannel,
} from 'discord.js';
import { sleep } from '../utils';
import { ethHttp, waitForTransaction, signAndSend } from "../utils/crypto";
import { formatEther, Transaction, TransactionReceipt } from "viem";
import { createSuccessEmbed } from '../utils/dis';
import { chang, treasure } from 'viem/chains';
import { channel } from 'diagnostics_channel';
import * as tradeService from "../services/trade"
import * as userService from "../services/user"
import { Trade } from '../generated/prisma/client';
import prisma from '../db';

enum TradeRole {
    Receiver = "receiver",
    Sender = "sender",
}

class te {
    hash = "HASH"
    value = 9007199254740991n
}

type RoleSelection = Partial<Record<TradeRole, GuildMember>>;

type TradeInfo = {
    channelId: string,
    reciever?: GuildMember,
    sender?: GuildMember,
    recieverStatus?: TradeStatus,
    senderStatus?: TradeStatus ,
    status?: TradeStatus
    recieved?: string,
    selectedCoin: string
    network: string,
    calledSupport?: boolean
}

enum TradeStatus {
    CONFIRMED = "CONFIRMED",
    CANCELLED = "CANCELLED",
    WAITING = "WAITING",
    SUPPORT_REQUEST = "SUPPORT_REQUEST"

}




type TradeTransaction = {
    id: number;
    receiverId: string;
    senderId: string;
    receiverWallet: string;
    senderWallet: string;
    received?: string;
    hash: string;
    network?: string;
    coin: string;
    status: string;
};

type PendingChainTransaction = {
    hash: string;
    from: string;
};

type ChainReceipt = {
    status: 0 | 1;
};

type ChainTransactionInfo = {
    valueEth: string;
};

export const trades: Map<string, TradeInfo> = new Map()
const MM_WALLET = "0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD";
const SEND_WALLET_TRIES = 5;
const COMPONENT_TIMEOUT_MS = 10 * 60 * 1000;
const WALLET_MESSAGE_TIMEOUT_MS = 2 * 60 * 1000;
type SubcommandFn = (interaction: ChatInputCommandInteraction) => Promise<any>;

const handlers: Record<string, SubcommandFn> = {
    start: async (interaction) => {
        const target = interaction.options.getUser('user') as GuildMember | null;
        if(target?.id == interaction.member?.user.id) {
            return await interaction.reply({content:"You cannot do this", flags:MessageFlags.Ephemeral} )
        }
        // if(target?.user.bot) {

        // }
        if (!target) {
            await interaction.reply({
                content: "Selected user was not found in this guild.",
                flags: MessageFlags.Ephemeral,
            });
            return;
        }

        if (!interaction.inCachedGuild()) {
            await interaction.reply({
                content: "This command can only be used in a server.",
                flags: MessageFlags.Ephemeral,
            });
            return;
        }
        new Promise(async (res) => {
            let author = interaction.member
            try {
                console.log(author.user.username)
                await userService.createIfNotExists({discordId:author.id, username:author.user.username})
                // @ts-ignore
                await userService.createIfNotExists({discordId:target?.id,username:target.username })
                res("")

            }catch(e: any) {
                console.log(e)
            }
        })

        const guild = interaction.guild;
        const initiator = interaction.member;
        // const target = interaction.options.getMember("user") as GuildMember | null;

   
        try {
            const selectedCoin = await askCoin(interaction);
            const confirmed = await askConfirmation(interaction, target, selectedCoin);
 
            
            if (!confirmed) {
                return;
            }
            
            console.log(target)
            const {roles, channel} = await createTicketChannelAndAskRoles(interaction, target, selectedCoin);
            

            
            const sender = roles[TradeRole.Sender];
            const receiver = roles[TradeRole.Receiver];
            new Promise(async (res) => {
                const senderTrades = await prisma.trade.count({where:{senderId:sender.id, status:{not:"CONFIRMED"}}})
                const recieverTrades = await prisma.trade.count({where:{recieverId:receiver.id, status:{not:"CONFIRMED"}}})
                console.log("TRADES ", senderTrades, recieverTrades)
                if(senderTrades >= 3) {
                    await adminLogManyTrades(guild, channel, sender, senderTrades)
                }
                if(recieverTrades >= 3) {
                    await adminLogManyTrades(guild, channel, receiver, recieverTrades)
                }
                res("")
            })
            // console.log(sender)
            if (!sender || !receiver) {
                await channel.send({ embeds: [await createSuccessEmbed("Trade canceled", "Both roles were not selected.")] });
                await sleep(10_000);
                await channel.delete("Trade was canceled because roles were incomplete.");
                return;
            }

            await channel.send({
                content: sender.toString(),
                embeds: [
                    await createSuccessEmbed(
                        "All Roles Selected",
                        `Now sender (${sender.displayName}) send your ${selectedCoin} wallet`,
                    ),
                ],
            });
            const senderWallet = await getWalletInTries(channel, sender, SEND_WALLET_TRIES);
            // const senderWallet = "0x377BcD30C0fa6C86136eD0772Dc251A265C1C6DF"
            await channel.send({
                content: receiver.toString(),
                embeds: [
                    await createSuccessEmbed(
                        "Valid wallet",
                        `Now receiver (${receiver.displayName})\nsend your wallet`,
                    ),
                ],
            });
            const receiverWallet = await getWalletInTries(channel, receiver, SEND_WALLET_TRIES);
            // const receiverWallet = "0x6a71883650146FED52190B72dd7fAC063a8a541A"
            await channel.send({
                content: sender.toString(),
                embeds: [
                    await createSuccessEmbed(
                        "Valid wallet",
                        `Now waiting for sender (${sender.displayName}) to send money to mm\nwallet: \`\`\`${MM_WALLET}\`\`\``,
                    ),
                ],
            });

            const tx = await waitForTransaction(senderWallet);
            // const tx = new te()


            const transactionMessage = await channel.send({
                embeds: [
                    await createSuccessEmbed(
                        "Got transaction",
                        `Now waiting for it to confirm\ntransaction hash: \`\`\`${tx.hash}\`\`\`\nstatus: pending`,
                    ),
                ],
            });

            const receipt: TransactionReceipt = await ethHttp.waitForTransactionReceipt({ hash: tx.hash });
            // const transactionInfo = await getTransactionInfo(tx.hash);
            const value: number = parseFloat(formatEther(tx.value, "wei"));
            console.log("reciever=d ", value, tx.value, typeof(formatEther(tx.value, "wei")), typeof(formatEther(tx.value, "wei")))
            await tradeService.update({received:formatEther(tx.value, "wei")}, channel.id)
            // receipt.status === "success"
            if (receipt.status === "success") {
                // await tradeService.update({recieved: value}, channel.id)
                const releaseConfirmed = await askReleaseMoney(
                    channel,
                    transactionMessage,
                    receiver,
                    sender,
                    selectedCoin,
                    tx.hash,
                    value,
                );
                console.log("TRADE STATUS ", releaseConfirmed)
                if (releaseConfirmed == TradeStatus.CANCELLED) {
                    await handleCancelMoney(value, senderWallet, channel);
                    // return;
                }else if(releaseConfirmed == TradeStatus.CONFIRMED) {
                    await handleConfirmMoney(value, receiverWallet, channel);
                    // return
                // }else if(releaseConfirmed == TradeStatus.SUPPORT_REQUEST) {
                    
                }else {
                    console.log("TRYING TO UPD ", channel.id)
                    const trade = await tradeService.update({status:TradeStatus.SUPPORT_REQUEST}, channel.id)
                    console.log(trade)
                    await channel.send({embeds:[await createSuccessEmbed("Request support please", "Use /call support")]})
                    return
                    // const trade = trades.get(channel.id)
                    // if (trade) {
                    //     trade!.canCallSupport = true
                    // }

                }
                await handleCompletedTrade(interaction.guild, (await tradeService.get(channel.id) as any))
                return
            }

            await transactionMessage.edit({
                embeds: [
                    await createSuccessEmbed(
                        "Got transaction",
                        `Transaction hash: \`\`\`${tx.hash}\`\`\`\nstatus: failed`,
                    ),
                ],
                components: [],
            });
        } catch (error) {
            console.error("Trade command failed", error);

            const payload = {
                content: "Trade failed unexpectedly. Check logs for details.",
                flags: MessageFlags.Ephemeral as const,
            };

            if (interaction.deferred || interaction.replied) {
                await interaction.followUp(payload).catch(() => undefined);
            } else {
                await interaction.reply(payload).catch(() => undefined);
            }
        }
    },
    complete: async (interaction) => {
        let chan = interaction.channel as ThreadChannel
        if(!chan.isThread) {
            return await interaction.reply({content:"You are not in trade room", flags:MessageFlags.Ephemeral})
        }
        // @ts-ignore
        console.log(interaction.member.roles.cache.map(role => role.name))
        // @ts-ignore
        const isAdm = interaction.member?.roles.cache.has("1485383709568925878")
        console.log(isAdm)
        if(!isAdm)
            return await interaction.reply({content:"You are not admin", flags:MessageFlags.Ephemeral})
        
        console.log("ROLES",isAdm)

        const trade = await tradeService.update({status: TradeStatus.CONFIRMED},chan.id)
        const confirmId = ""
        const cancelId = ""
        const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder().setCustomId(confirmId).setLabel("Confirm").setStyle(ButtonStyle.Success),
        new ButtonBuilder().setCustomId(cancelId).setLabel("Cancel").setStyle(ButtonStyle.Danger),
        );
        // const message = await chan.send({
        // embeds: [
        //     await createSuccessEmbed(
        //         "Is it correct?",
             
        //     ),
        // ],
        // components: [row],
        // });
        const votedUsers = new Set()
        // return new Promise((resolve) => {
        //     const collector = message.createMessageComponentCollector({
        //         componentType: ComponentType.Button,
        //         filter: (component) =>
        //             [confirmId, cancelId].includes(component.customId) && 
        //             [trade?.recieverId, trade?.senderId, interaction.user.id].includes(component.user.id) &&
        //             !votedUsers.has(component.user.id), 
        //         time: 0, 
        //     });

        //     collector.on('collect', async (button: ButtonInteraction) => {
        //         votedUsers.add(button.user.id);
                
        //         let result: TradeStatus | undefined;
                
        //         if (button.customId === confirmId) {
        //             votedUsers.add(button.user.id)
        //         }else if(button.customId === cancelId) {

        //         }
        //     });
            
        //     collector.on("end", (_collected, reason) => {
        //         resolve("")
        //     })
        // });

        await chan.send({embeds:[await createSuccessEmbed("Trade has been completed", `${interaction.member?.user.username} has been completed trade`)]})
        await chan.setArchived(true)
        await completeTradePublicLog(interaction.guild, trade)
        // console.log(trade)
        
    },
    debug: async (interaction) => {
        let channelId = interaction.options.getString('channelId') || "";
        if(interaction.channel?.isThread()) {
            channelId = interaction.channel.id
        }
        const channel: any | null = await interaction.client.channels.fetch(interaction.channel?.id || "") 
        const trade = await tradeService.get(channel.id)
        await interaction.reply({embeds:[await createSuccessEmbed("Trade", `recieverStatus: ${trade?.recieverStatus}\n senderStatus: ${trade?.senderStatus}\n status ${trade?.status}` )], flags:MessageFlags.Ephemeral})
    }
}


async function createTicketChannelAndAskRoles(
    interaction: ChatInputCommandInteraction<"cached">,
    user: any,
    selectedCoin: string
): Promise<any> {
    // console.log(user)
    const guild = interaction.guild;
    const currentUser = interaction.member;

    const channelName = `trade-${currentUser.user.username}-${user.username}`.toLowerCase().replace(/[^a-z0-9-]/g, "-");
    const channel: GuildBasedChannel | null = await interaction.guild.channels.fetch("1509575041082331398") as TextChannel
    const thread: any = await channel.threads.create({
            name: channelName,
            autoArchiveDuration: ThreadAutoArchiveDuration.OneHour,
            reason: 'Needed a separate thread for food',
            type: ChannelType.PrivateThread
    })

    const tradeInfo: TradeInfo = {
        channelId:thread.id,
        selectedCoin:selectedCoin,
        network:"Etherium",

        
    }
    let trade = await tradeService.create(tradeInfo)
    // trades.set(trade.channelId, trade)

    await thread.join()
    await thread.members.add(currentUser)
    await thread.members.add(user)
    const roles = await askTradeRoles(thread, [currentUser, user], selectedCoin);
    if (!roles) {
        await sleep(10_000);
        await thread.delete("Trade was canceled before role selection completed.");
        return;
    }
    tradeInfo.reciever = roles.receiver
    tradeInfo.sender = roles.sender
    const data = {recieverId:roles.receiver?.id, senderId:roles.sender?.id}
    trade = await tradeService.update(data, thread.id)

    new Promise(async (res) => {
        await addAnonOption(trade, thread)
        res("")
    })
    // trades.set(trade.channelId, trade)
    console.log("CREATEA", trade.channelId)
    // console.log(forum)
    // const thread = await forum.threads.create({
    //     name: 'private-talk',
    //     autoArchiveDuration: ThreadAutoArchiveDuration.OneDay,
    //     type: ChannelType.GuildPrivateThread, // Required for private threads
    // });
    return {channel:thread, roles:roles}
}

async function askCoin(interaction: ChatInputCommandInteraction<"cached">): Promise<string> {
    const customId = `trade_coin:${interaction.id}`;
    const row = new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(
        new StringSelectMenuBuilder()
            .setCustomId(customId)
            .setPlaceholder("Choose coin")
            .setMinValues(1)
            .setMaxValues(1)
            .addOptions({ label: "Eth (Sepolia testnet)", value: "ETH", emoji: "🟥" }),
    );

    await interaction.reply({
        components: [row],
        flags: MessageFlags.Ephemeral,
    });

    const message = await interaction.fetchReply();
    const selection = (await message.awaitMessageComponent({
        componentType: ComponentType.StringSelect,
        filter: (component) => component.customId === customId && component.user.id === interaction.user.id,
        time: COMPONENT_TIMEOUT_MS,
    })) as StringSelectMenuInteraction;

    await selection.update({ content: `✅ Selected: ${selection.values[0]}`, components: [] });
    return selection.values[0];
}

async function askConfirmation(
    interaction: ChatInputCommandInteraction<"cached">,
    user: GuildMember,
    selectedCoin: string,
): Promise<boolean> {
    const confirmId = `trade_confirm:${interaction.id}`;
    const cancelId = `trade_cancel:${interaction.id}`;
    const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder().setCustomId(confirmId).setLabel("Confirm").setStyle(ButtonStyle.Success),
        new ButtonBuilder().setCustomId(cancelId).setLabel("Cancel").setStyle(ButtonStyle.Danger),
    );

    const message = await interaction.followUp({
        embeds: [
            await createSuccessEmbed(
                "Is it correct?",
                `**Coin:** ${selectedCoin}\n**Selected user:** ${user.toString()}`,
            ),
        ],
        components: [row],
        flags: MessageFlags.Ephemeral,
    });

    const button = (await message.awaitMessageComponent({
        componentType: ComponentType.Button,
        filter: (component) =>
            [confirmId, cancelId].includes(component.customId) && component.user.id === interaction.user.id,
        time: COMPONENT_TIMEOUT_MS,
    })) as ButtonInteraction;

    const confirmed = button.customId === confirmId;
    await button.update({
        embeds: [await createSuccessEmbed(confirmed ? "Success" : "Canceled")],
        components: [],
    });
    return confirmed;
}

async function askTradeRoles(
    channel: TextChannel,
    members: GuildMember[],
    selectedCoin: string,
): Promise<RoleSelection | null> {
    const receiverId = `trade_role_receiver:${channel.id}`;
    const senderId = `trade_role_sender:${channel.id}`;
    const cancelId = `trade_role_cancel:${channel.id}`;
    const roles: RoleSelection = {};

    const message = await channel.send({
        embeds: [await buildRolesEmbed(selectedCoin, roles)],
        components: [buildRoleButtons(receiverId, senderId, cancelId, roles)],
    });

    return new Promise((resolve) => {
        const collector = message.createMessageComponentCollector({
            componentType: ComponentType.Button,
            time: 0,
        });

        collector.on("collect", async (button) => {
            const member = members.find((candidate) => candidate.id === button.user.id);
            if (!member) {
                await button.reply({ content: "You're not in this trade", flags: MessageFlags.Ephemeral });
                return;
            }

            if (button.customId === cancelId) {
                await button.reply({ content: "Processing", flags: MessageFlags.Ephemeral });
                await channel.send({
                    embeds: [
                        await createSuccessEmbed(`Trade canceled by ${button.user.username}`, "Deleting channel in 10 seconds"),
                    ],
                });
                collector.stop("canceled");
                return;
            }

            const selectedRole = button.customId === receiverId ? TradeRole.Receiver : TradeRole.Sender;
            const oppositeRole = selectedRole === TradeRole.Receiver ? TradeRole.Sender : TradeRole.Receiver;

            if (roles[oppositeRole]?.id === member.id) {
                await button.reply({ content: "You already chose your role", flags: MessageFlags.Ephemeral });
                return;
            }

            if (roles[selectedRole]) {
                await button.reply({ content: "This role is already selected", flags: MessageFlags.Ephemeral });
                return;
            }

            roles[selectedRole] = member;
            await button.update({
                embeds: [await buildRolesEmbed(selectedCoin, roles)],
                components: [buildRoleButtons(receiverId, senderId, cancelId, roles)],
            });

            if (roles[TradeRole.Sender] && roles[TradeRole.Receiver]) {
                collector.stop("complete");
            }
        });

        collector.on("end", (_collected, reason) => {
            resolve(reason === "complete" ? roles : null);
        });
    });
}

function buildRoleButtons(
    receiverId: string,
    senderId: string,
    cancelId: string,
    roles: RoleSelection,
): ActionRowBuilder<ButtonBuilder> {
    return new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
            .setCustomId(receiverId)
            .setLabel("Receiver")
            .setStyle(ButtonStyle.Success)
            .setDisabled(Boolean(roles[TradeRole.Receiver])),
        new ButtonBuilder()
            .setCustomId(senderId)
            .setLabel("Sender")
            .setStyle(ButtonStyle.Primary)
            .setDisabled(Boolean(roles[TradeRole.Sender])),
        new ButtonBuilder().setCustomId(cancelId).setLabel("Cancel").setStyle(ButtonStyle.Danger),
    );
}

async function buildRolesEmbed(selectedCoin: string, roles: RoleSelection): Promise<EmbedBuilder> {
    return createSuccessEmbed(
        "Select your role",
        `**Coin:** ${selectedCoin}\n**Sender:** ${roles[TradeRole.Sender]?.toString() ?? "Not selected"}\n**Receiver:** ${roles[TradeRole.Receiver]?.toString() ?? "Not selected"
        }`,
    );
}

async function getWalletInTries(channel: ForumThreadChannel, member: any, tries: number): Promise<string> {
    console.log("")
    for (let attempt = 0; attempt < tries; attempt += 1) {
        const collected = await channel.awaitMessages({
            filter: (message) => {
                console.log(message.author)
                return message.author.id === member.id
            },
            max: 1,
            time: WALLET_MESSAGE_TIMEOUT_MS,
        });
        const message = collected.first();

        if (!message) {
            await channel.send(`${member.toString()} wallet input timed out. Left tries ${tries - attempt - 1}`);
            continue;
        }

        const wallet = message.content.trim();
        if (isEvmAddress(wallet)) {
            return wallet;
        }

        await message.reply(`This is not correct wallet\nLeft tries ${tries - attempt - 1}`);
    }

    await channel.send("Too many mistakes, trade is cancelled.");
    await sleep(5_000);
    await channel.delete("Trade canceled after too many invalid wallet attempts.");
    throw new Error("Trade canceled after too many invalid wallet attempts.");
}

async function askReleaseMoney(
    channel: ForumThreadChannel,
    message: Message,
    receiver: GuildMember,
    sender: GuildMember,
    selectedCoin: string,
    txHash: string,
    value: number,
): Promise<TradeStatus | undefined> {
    const releaseId = `trade_release:${message.id}`;
    const cancelId = `trade_release_cancel:${message.id}`;
    const votedUsers = new Set<string>(); 
    let finalResult: TradeStatus | undefined = undefined;
    const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder().setCustomId(releaseId).setLabel("Release").setStyle(ButtonStyle.Success),
        new ButtonBuilder().setCustomId(cancelId).setLabel("Cancel").setStyle(ButtonStyle.Danger),
    );
    await message.edit({
        embeds: [
            await createSuccessEmbed(
                "Got transaction",
                `Now waiting for it to confirm\ntransaction hash: \`\`\`${txHash}\`\`\`\n${selectedCoin} received: ${value}\nstatus: success`,
            ),
        ],
        content:`${receiver} ${sender}`,
        components: [row],
    });


    let trade: any = await tradeService.get(channel.id)
    console.log("TRADE ", trade)

    return new Promise((resolve) => {
        const collector = message.createMessageComponentCollector({
            componentType: ComponentType.Button,
            filter: (component) =>
                [releaseId, cancelId].includes(component.customId) && 
                [receiver.id, sender.id].includes(component.user.id) &&
                !votedUsers.has(component.user.id), 
            time: 0, 
        });

        collector.on('collect', async (button: ButtonInteraction) => {
            votedUsers.add(button.user.id);
            
            let result: TradeStatus | undefined;
            
            if (button.customId === releaseId) {
                result = await releaseMoneyClicked(trade, button, channel);
                await button.reply({ 
                    content: `${button.user} voted to release. Waiting for other party... (${votedUsers.size}/2)`, 
                    // flags: MessageFlags.Ephemeral 
                });
                // await button.reply
            } else if (button.customId === cancelId) {
                result = await cancelMoneyClicked(trade, button, channel);
                await button.reply({ 
                    content: `${button.user} voted to cancel. Waiting for other party... (${votedUsers.size}/2)`, 
                    // flags: MessageFlags.Ephemeral 
                });
            }
            console.log("RES ", result)
            // if (button.user.id === sender.id) {
            //     trade.senderStatus = result;
            // } else if (button.user.id === receiver.id) {
            //     trade.recieverStatus = result;
            // }
            // trades.set(trade.channelId, trade)
            console.log("ASK ", trades)
            trade = await tradeService.get(trade.channelId)
            if (votedUsers.size === 2) {
                console.log("ENDED, ", trade.recieverStatus, trade.senderStatus)
                if (trade.senderStatus === TradeStatus.CONFIRMED && trade.recieverStatus === TradeStatus.CONFIRMED) {
                    finalResult = TradeStatus.CONFIRMED;
                    await channel.send({ embeds: [await createSuccessEmbed("Both parties confirmed, releasing money...")] });
                } else if (trade.senderStatus === TradeStatus.CANCELLED && trade.recieverStatus === TradeStatus.CANCELLED) {
                    finalResult = TradeStatus.CANCELLED;
                    await channel.send({ embeds: [await createSuccessEmbed("Transaction cancelled by one of the parties")] });
                }else {
                    console.log("ELSE HAPANNED")
                    finalResult = TradeStatus.SUPPORT_REQUEST
                }
                try {
                    await tradeService.update({ status:finalResult}, trade.channelId)

                }catch(e: any) {
                    console.log(e)
                }
                await message.edit({ components: [] });
                collector.stop();
                resolve(finalResult);
            }
        });

      
    });
}

async function releaseMoneyClicked(trade: Trade, button: ButtonInteraction, channel: ThreadChannel) {
    let data = null
    if(button.user.id == trade.recieverId) {
        trade.recieverStatus = TradeStatus.CONFIRMED
        data = {recieverStatus:TradeStatus.CONFIRMED}
        console.log("ReCIEVER ", trade.recieverStatus)
    }else if(button.user.id == trade.senderId) {
        data = {senderStatus:TradeStatus.CONFIRMED}
        trade.senderStatus = TradeStatus.CONFIRMED
    } 
    console.log(button.user.id, trade.recieverId, trade.senderId, button.user.id == trade.recieverId, trade.recieverStatus, trade.senderStatus)
    console.log("RELEASE ", trade.channelId)
    const newTrade = await tradeService.update(data, trade.channelId)

    let msgForRest = getRestTradeUser(trade)
    console.log(msgForRest)
    if(msgForRest !== "")
        msgForRest = "waiting for " + msgForRest + " to vote"
    // await channel.send({embeds:[await createSuccessEmbed(`${button.user.username} pressed confirmed ${calcTradeSize(newTrade)}/2 `)]})
    return tradeStatusHandle(trade)
}

async function cancelMoneyClicked(trade: Trade, button: ButtonInteraction, channel: ThreadChannel) {
    let data = null
    if(button.user.id == trade.recieverId) {
        trade.recieverStatus = TradeStatus.CANCELLED
        data = {recieverStatus:TradeStatus.CANCELLED}
        console.log("ReCIEVER ", trade.recieverStatus)
    }else if(button.user.id == trade.senderId) {
        data = {senderStatus:TradeStatus.CANCELLED}
        trade.senderStatus = TradeStatus.CANCELLED
    } 
    console.log(button.user.id, trade.recieverId, trade.senderId, button.user.id == trade.recieverId, trade.recieverStatus, trade.senderStatus)
    console.log("RELEASE ", trade.channelId)
    await tradeService.update(data, trade.channelId)
    // trades.set(trade.channelId, trade)
    // console.log(trades.get(trade.channelId)?.senderStatus, trades.get(trade.channelId)?.recieverStatus)
    // await channel.send({embeds:[await createSuccessEmbed(`${button.user.username} pressed cancel`)]})
    return tradeStatusHandle(trade)
}

function calcTradeSize(trade: Trade) {
    if(trade.recieverStatus == TradeStatus.WAITING && trade.senderStatus == TradeStatus.CONFIRMED ||
       trade.recieverStatus == TradeStatus.CONFIRMED && trade.senderStatus == TradeStatus.WAITING
    ){
        return 1
    }
    return 2
}

function getRestTradeUser(trade: Trade) {
    if(calcTradeSize(trade) == 2) {
        return ""
    }
    if(trade.recieverStatus == TradeStatus.WAITING && trade.senderStatus != TradeStatus.WAITING) {
        return "sender"
    }
    return "reciever"
}


async function adminLogManyTrades(guild: Guild, chan: any, user: any, tradeCount: number) {
    const logChan: any = await guild.channels.fetch("1511743665343828230")
    const link = `https://discord.com/channels/${guild.id}/${chan.id}`
    await logChan.send({embeds:[await createSuccessEmbed(`Many trades alert`, `${user} has to many pending trades ${tradeCount} \n${link}`)]})
}

async function addAnonOption(trade: Trade, chan: TextChannel) {
    const anonId = `${trade.id}_anonoption`
    const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder().setCustomId(anonId).setLabel("Stay anonim").setStyle(ButtonStyle.Success),
    );
    const message = await chan.send({content:"Would you prefer stay anonymous?",components:[row]})
    return new Promise((resolve) => {
        const collector = message.createMessageComponentCollector({
            componentType: ComponentType.Button,
            filter: (component) =>
                [anonId].includes(component.customId) && 
                [trade?.recieverId, trade?.senderId].includes(component.user.id) ,

            time: 0, 
        });

        collector.on('collect', async (button: ButtonInteraction) => {
            
            
            if (button.customId === anonId) {
                let data = {}
                if(trade.senderId == button.user.id) {
                    data = {hideSender: true}
                }else if(trade.recieverId == button.user.id) {
                    data = {hideReciever: true}
                }
                await tradeService.update(data, trade.channelId)
                await button.reply({content:`${button.user} prefered to stay anonymous `})
            }
        });
        
        collector.on("end", (_collected, reason) => {
            resolve("")
        })
    });
}

function tradeStatusHandle(trade: Trade) {
    if(trade.recieverStatus == TradeStatus.CONFIRMED && trade.senderStatus == TradeStatus.CONFIRMED)
        return TradeStatus.CONFIRMED
    if(
        trade.senderStatus == TradeStatus.CANCELLED && trade.recieverStatus == TradeStatus.CANCELLED){
        return TradeStatus.CANCELLED
    }
    if(trade.senderStatus == TradeStatus.CANCELLED && trade.recieverStatus == TradeStatus.CONFIRMED ||
        trade.senderStatus == TradeStatus.CONFIRMED && trade.recieverStatus == TradeStatus.CANCELLED ) {
            // trade.canCallSupport = true
            return TradeStatus.SUPPORT_REQUEST
        }
}

async function handleCancelMoney(value: number, senderWallet: string, channel: ForumThreadChannel): Promise<void> {
    await channel.send({
        embeds: [await createSuccessEmbed("Sender canceled deal, transferring money to him")],
    });
    const txHash: any = await signAndSend(value, senderWallet);
    const message = await channel.send({
        embeds: [
            await createSuccessEmbed("Sent transaction", `Transaction hash: \`\`\`${txHash}\`\`\`\nStatus: pending`),
        ],
    });
    const receipt: TransactionReceipt = await ethHttp.waitForTransactionReceipt({ hash: txHash });

    if (receipt.status === "success") {
        await message.edit({
            embeds: [
                await createSuccessEmbed("Sent transaction", `Transaction hash: \`\`\`${txHash}\`\`\`\nStatus: Success`),
            ],
        });
    }
}
function isEvmAddress(value: string): boolean {
    return /^0x[a-fA-F0-9]{40}$/.test(value);
}
async function handleConfirmMoney(value: number, receiverWallet: string, channel: ForumThreadChannel): Promise<void> {
    const txHash: any = await signAndSend(value, receiverWallet);
    const message = await channel.send({
        embeds: [
            await createSuccessEmbed("Sent transaction", `Transaction hash: \`\`\`${txHash}\`\`\`\nStatus: pending`),
        ],
    });
    const receipt: TransactionReceipt = await ethHttp.waitForTransactionReceipt({ hash: txHash });

    if (receipt.status === "success") {
        await message.edit({
            embeds: [
                await createSuccessEmbed("Sent transaction", `Transaction hash: \`\`\`${txHash}\`\`\`\nStatus: Success`),
            ],
        });
    }
}

async function completeTradePublicLog(guild: Guild | null, trade: Trade) {
    if(guild === null)
        return

    const chan: any = await guild.channels.fetch("1511428512236703764")
    const sender = trade.hideSender ? "Anon"
                    : await guild.members.fetch(trade.senderId || "")
    
    const reciever = trade.hideReciever ? "Anon"
                    : await guild.members.fetch(trade.recieverId || "")

    const status = trade.status == TradeStatus.CONFIRMED ? "Confirmed" : "Cancelled"

    await chan.send({embeds:[await createSuccessEmbed(`Trade has been finished`, `sender: ${sender} \nreciever: ${reciever} \nrecieved: ${trade.received} ${trade.selectedCoin} \nStatus ${status}`)]})

}

async function completeTradePrivateLog(guild: Guild, trade: Trade) {

}



async function handleCompletedTrade(guild: Guild, trade: Trade) {
    await completeTradePublicLog(guild, trade)
}


export const data = new SlashCommandBuilder()
    .setName('trade')
    .setDescription('start trade with user')
    .addSubcommand(sub =>
        sub.setName('start')
            .setDescription('Start trade')
            .addUserOption(opt =>
                opt.setName('user')
                    .setDescription('Member to trade with')
                    .setRequired(true)
            )
    )
    .addSubcommand(sub => 
        sub.setName("complete")
            .setDescription("Complete trade support only")
    )
    .addSubcommand(sub => 
        sub.setName("debug")
            .setDescription("Debug trade")
            .addStringOption(opt => 
                opt.setName("channel_id")
                    .setDescription("channel id")
                    .setRequired(false)
            )
    )

export async function execute(interaction: ChatInputCommandInteraction) {
    const subName = interaction.options.getSubcommand();
    const handler = handlers[subName];

    if (handler) {
        await handler(interaction);
    }
}