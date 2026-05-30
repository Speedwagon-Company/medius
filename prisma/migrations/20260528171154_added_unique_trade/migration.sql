/*
  Warnings:

  - A unique constraint covering the columns `[channelId]` on the table `Trade` will be added. If there are existing duplicate values, this will fail.

*/
-- CreateIndex
CREATE UNIQUE INDEX "Trade_channelId_key" ON "Trade"("channelId");
