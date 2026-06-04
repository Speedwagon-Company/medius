/*
  Warnings:

  - A unique constraint covering the columns `[guildId]` on the table `Config` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "Config" ADD COLUMN "guildId" TEXT;
ALTER TABLE "Config" ADD COLUMN "privateLogChanId" TEXT;
ALTER TABLE "Config" ADD COLUMN "publicLogChanId" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "Config_guildId_key" ON "Config"("guildId");
