import prisma from "../db";


export async function createIfNotExists(userData: any) {
    if(await prisma.user.findUnique({where:{discordId:userData.discordId}}))
        return
    return await prisma.user.create({data:userData})
}