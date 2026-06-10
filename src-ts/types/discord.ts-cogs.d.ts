declare module "discord.ts-cogs" {
  import {
    Client,
    ClientOptions,
    Collection,
    CommandInteraction,
    RESTPostAPIChatInputApplicationCommandsJSONBody,
    SlashCommandBuilder,
  } from "discord.js";

  export enum ArgumentType {
    String = 0,
    Integer = 1,
    Number = 2,
    Boolean = 3,
    User = 4,
    Channel = 5,
    Role = 6,
    Mentionable = 7,
    Attachment = 8,
  }

  export class CommandArgument {
    constructor(name: string, type?: ArgumentType, description?: string, required?: boolean);
    get name(): string;
    get description(): string;
    get type(): ArgumentType;
    get required(): boolean;
  }

  export class SlashCommandMetadata {
    static COMMAND_METADATA_KEY: string;
    constructor(commandName: string, description?: string);
    get commandName(): string;
    get description(): string;
    addArg(arg: CommandArgument): void;
    getArgs(): CommandArgument[];
  }

  export abstract class SlashCommand {
    constructor(metadata: SlashCommandMetadata);
    get metadata(): SlashCommandMetadata;
    build(): SlashCommandBuilder;
    abstract call(interaction: CommandInteraction): Promise<void>;
  }

  export abstract class Cog {
    static command(name?: string, description?: string): MethodDecorator;
    static argument(name: string, type?: ArgumentType, description?: string, required?: boolean): MethodDecorator;
    getCommands(): SlashCommand[];
  }

  export class CogsClient extends Client {
    constructor(options: ClientOptions);
    cogs: Set<string>;
    commands: Collection<string, SlashCommand>;
    addCog(cog: Cog): void;
    syncCommands(token: string, clientId: string, guildId?: string): Promise<void>;
  }

  export type { RESTPostAPIChatInputApplicationCommandsJSONBody };
}
