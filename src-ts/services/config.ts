import { configCache } from "../storage";


export async function get(guildId: string) {
    configCache.get(guildId)
}