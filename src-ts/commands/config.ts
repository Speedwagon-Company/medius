import { SlashCommandBuilder, ChatInputCommandInteraction } from 'discord.js';

// Описываем тип обработчика для типизации карты
type SubcommandFn = (interaction: ChatInputCommandInteraction) => Promise<any>;

// Карта обработчиков для подкоманд config
const handlers: Record<string, SubcommandFn> = {
    color: async (interaction) => {
        const color = interaction.options.getString('value');
        // Логика смены цвета (например, сохранение в БД)
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
                    .addChoices(
                        { name: 'Красный', value: 'Red' },
                        { name: 'Синий', value: 'Blue' },
                        { name: 'Зеленый', value: 'Green' }
                    )
            )
    );

export async function execute(interaction: ChatInputCommandInteraction) {
    const subName = interaction.options.getSubcommand();
    const handler = handlers[subName];

    if (handler) {
        await handler(interaction);
    }
}