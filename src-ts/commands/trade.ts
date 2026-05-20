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
} from 'discord.js';
import { sleep } from '../utils';
import { ethHttp, waitForTransaction, signAndSend } from "../utils/crypto";
import { formatEther, Transaction, TransactionReceipt } from "viem";
import { createSuccessEmbed } from '../utils/dis';
import { treasure } from 'viem/chains';

enum TradeRole {
    Receiver = "receiver",
    Sender = "sender",
}

type RoleSelection = Partial<Record<TradeRole, GuildMember>>;

type TradeInfo = {
    channelId: string,
    reciever?: GuildMember,
    sender?: GuildMember,
    recieverStatus?: TradeStatus,
    senderStatus?: TradeStatus ,
    recieved?: string,
    selectedCoin: string
    network: string,
    canCallSupport: boolean
}

enum TradeStatus {
    "CONFIRMED",
    "CANCELLED",
    "WAITING",
    "SUPPORT_REQUEST"

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
    trade: async (interaction) => {
        const target = interaction.options.getUser('user') as GuildMember | null;
        if (!interaction.inCachedGuild()) {
            await interaction.reply({
                content: "This command can only be used in a server.",
                flags: MessageFlags.Ephemeral,
            });
            return;
        }

        const guild = interaction.guild;
        const initiator = interaction.member;
        // const target = interaction.options.getMember("user") as GuildMember | null;

        if (!target) {
            await interaction.reply({
                content: "Selected user was not found in this guild.",
                flags: MessageFlags.Ephemeral,
            });
            return;
        }

        try {
            const selectedCoin = await askCoin(interaction);
            const confirmed = await askConfirmation(interaction, target, selectedCoin);

            if (!confirmed) {
                return;
            }
            console.log(target)
            const {roles, channel} = await createTicketChannelAndAskRoles(interaction, target, selectedCoin);
            await createTrade(initiator.id, target.id);



            const sender = roles[TradeRole.Sender];
            const receiver = roles[TradeRole.Receiver];
            console.log(sender)
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
            // TODO IMPLEMENT
            // const transaction = await createTransaction({
            //     receiverId: receiver.id,
            //     senderId: sender.id,
            //     senderWallet,
            //     receiverWallet,
            //     coin: selectedCoin,
            //     hash: tx.hash,
            // });

            // TODO: implement
            // await sendTransactionLog(
            //     guild,
            //     await createSuccessEmbed(
            //     "Created transaction",
            //     `Transaction id: ${transaction.id}\nHash: \`\`\`${tx.hash}\`\`\``,
            //     ),
            // );

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
            console.log("reciever=d ", value, tx.value, formatEther(tx.value, "wei"))


            if (receipt.status === "success") {
                // TODO : REFACTR
                // await updateTransactionStatus(transaction.id, "CONFIRMED");
                // await sendTransactionLog(
                // guild,
                // await createSuccessEmbed(
                //     "Updated transaction",
                //     `Transaction id: ${transaction.id}\nTransaction hash: \`\`\`${tx.hash}\`\`\`\nTransaction status: CONFIRMED`,
                // ),
                // );

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
                    return;
                }else if(releaseConfirmed == TradeStatus.CONFIRMED) {
                    await handleConfirmMoney(value, receiverWallet, channel);
                    return
                // }else if(releaseConfirmed == TradeStatus.SUPPORT_REQUEST) {
                    
                }
                await channel.send({embeds:[await createSuccessEmbed("Request support please")]})
                const trade = trades.get(channel.id)
                if (trade) {
                    trade!.canCallSupport = true
                }
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
    const forum: GuildBasedChannel | null = await interaction.guild.channels.fetch("1504040879697170573") as ForumChannel
    const thread = await forum.threads.create({
        name: channelName,
        autoArchiveDuration: ThreadAutoArchiveDuration.OneHour,
        reason: 'Needed a separate thread for food',
        message:{content:"Initiating trade"},
        
    });
    const trade: TradeInfo = {
        channelId:thread.id,
        selectedCoin:selectedCoin,
        network:"Etherium",
        canCallSupport:false
    }
    trades.set(trade.channelId, trade)
    await thread.members.add(currentUser)
    await thread.members.add(user)
    const roles = await askTradeRoles(thread, [currentUser, user], selectedCoin);
    if (!roles) {
        await sleep(10_000);
        await thread.delete("Trade was canceled before role selection completed.");
        return;
    }
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
            .addOptions({ label: "ETH", value: "ETH", emoji: "🟥" }),
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
    channel: ForumThreadChannel,
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
                        await createSuccessEmbed(`Trade canceled by ${button.user.toString()}`, "Deleting channel in 10 seconds"),
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
    const votedUsers = new Set<string>(); // Храним ID проголосовавших
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
        components: [row],
    });

    // const button = (await message.awaitMessageComponent({
    //     componentType: ComponentType.Button,
    //     filter: (component) =>
    //         [releaseId, cancelId].includes(component.customId) && component.user.id === receiver.id || component.user.id === sender.id,
    //     time: 0,
    // })) as ButtonInteraction;
    const trade: any = trades.get(channel.id)
    // let res = undefined
    // if (button.customId === releaseId) {
    //     res = await releaseMoneyClicked(trade, button, channel)
    // }else if(button.customId === cancelId) {
    //     res = await cancelMoneyClicked(trade, button, channel)


    // }

    // if(trade.senderStatus != TradeStatus.WAITING && trade.recieverStatus != TradeStatus.WAITING) {
    //     return res;

    // }
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
                    content: `✅ You voted to release. Waiting for other party... (${votedUsers.size}/2)`, 
                    flags: MessageFlags.Ephemeral 
                });
            } else if (button.customId === cancelId) {
                result = await cancelMoneyClicked(trade, button, channel);
                await button.reply({ 
                    content: `❌ You voted to cancel. Waiting for other party... (${votedUsers.size}/2)`, 
                    flags: MessageFlags.Ephemeral 
                });
            }
            
            // Обновляем статус в зависимости от голоса
            if (button.user.id === sender.id) {
                trade.senderStatus = result;
            } else if (button.user.id === receiver.id) {
                trade.recieverStatus = result;
            }
            
            // Проверяем, проголосовали ли оба
            if (votedUsers.size === 2) {
                // Определяем финальный результат
                if (trade.senderStatus === TradeStatus.CONFIRMED && trade.recieverStatus === TradeStatus.CONFIRMED) {
                    finalResult = TradeStatus.CONFIRMED;
                    await channel.send({ embeds: [await createSuccessEmbed("Both parties confirmed! Releasing money...")] });
                } else if (trade.senderStatus === TradeStatus.CANCELLED || trade.recieverStatus === TradeStatus.CANCELLED) {
                    finalResult = TradeStatus.CANCELLED;
                    await channel.send({ embeds: [await createSuccessEmbed("Transaction cancelled by one of the parties")] });
                }
                
                // Очищаем кнопки
                await message.edit({ components: [] });
                collector.stop();
                resolve(finalResult);
            }
        });

        // collector.on('end',async (_, reason) => {
        //     if (reason !== 'user') {
        //         // Таймаут или ошибка
        //         if (votedUsers.size < 2) {
        //             const notVoted = [sender.id, receiver.id].filter(id => !votedUsers.has(id));
        //             channel.send({ 
        //                 embeds: [await createErrorEmbed(`Timeout waiting for <@${notVoted[0]}> to vote`)] 
        //             });
        //             await message.edit({ components: [] });
        //         }
        //         resolve(TradeStatus.CANCELLED);
        //     }
        // });
    });
}

async function releaseMoneyClicked(trade: TradeInfo, button: ButtonInteraction, channel: ThreadChannel) {
    if(button.user.id == trade.reciever?.id) {
        trade.recieverStatus = TradeStatus.CONFIRMED
    }else if(button.user.id == trade.sender?.id) {
        trade.senderStatus = TradeStatus.CONFIRMED
    } 

    await channel.send({embeds:[await createSuccessEmbed(`${button.user.username} pressed confirmed`)]})
    return tradeStatusHandle(trade)
}

async function cancelMoneyClicked(trade: TradeInfo, button: ButtonInteraction, channel: ThreadChannel) {
    if(button.user.id == trade.reciever?.id) {
        trade.recieverStatus = TradeStatus.CANCELLED
    }else if(button.user.id == trade.sender?.id) {
        trade.senderStatus = TradeStatus.CANCELLED
    } 
    await channel.send({embeds:[await createSuccessEmbed(`${button.user.username} pressed cancel`)]})
    return tradeStatusHandle(trade)
}


function tradeStatusHandle(trade: TradeInfo) {
    if(trade.recieverStatus == TradeStatus.CONFIRMED && trade.senderStatus == TradeStatus.CONFIRMED)
        return TradeStatus.CONFIRMED
    if(
        trade.senderStatus == TradeStatus.CANCELLED && trade.recieverStatus == TradeStatus.CANCELLED){
        return TradeStatus.CANCELLED
    }
    if(trade.senderStatus == TradeStatus.CANCELLED && trade.recieverStatus == TradeStatus.CONFIRMED ||
        trade.senderStatus == TradeStatus.CONFIRMED && trade.recieverStatus == TradeStatus.CANCELLED ) {
            trade.canCallSupport = true
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



async function createTrade(user1DiscordId: string, user2DiscordId: string): Promise<void> {
    // TODO: port/import the project's DB create_trade implementation.
    void user1DiscordId;
    void user2DiscordId;
}


export const data = new SlashCommandBuilder()
    .setName('start')
    .setDescription('Запуск различных процессов')
    .addSubcommand(sub =>
        sub.setName('trade')
            .setDescription('Начать обмен с игроком')
            .addUserOption(opt =>
                opt.setName('user')
                    .setDescription('С кем вы хотите торговать?')
                    .setRequired(true)
            )
    );

export async function execute(interaction: ChatInputCommandInteraction) {
    const subName = interaction.options.getSubcommand();
    const handler = handlers[subName];

    if (handler) {
        await handler(interaction);
    }
}