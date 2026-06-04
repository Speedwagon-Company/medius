-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Trade" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "channelId" TEXT NOT NULL,
    "recieverStatus" TEXT NOT NULL DEFAULT 'WAITING',
    "senderStatus" TEXT NOT NULL DEFAULT 'WAITING',
    "status" TEXT NOT NULL DEFAULT 'WAITING',
    "selectedCoin" TEXT NOT NULL,
    "network" TEXT NOT NULL,
    "canCallSupport" BOOLEAN NOT NULL DEFAULT false,
    "recieved" TEXT,
    "hideSender" BOOLEAN NOT NULL DEFAULT false,
    "hideReciever" BOOLEAN NOT NULL DEFAULT false,
    "senderId" TEXT,
    "recieverId" TEXT,
    CONSTRAINT "Trade_senderId_fkey" FOREIGN KEY ("senderId") REFERENCES "User" ("discordId") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Trade_recieverId_fkey" FOREIGN KEY ("recieverId") REFERENCES "User" ("discordId") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Trade" ("canCallSupport", "channelId", "id", "network", "recieverId", "recieverStatus", "selectedCoin", "senderId", "senderStatus", "status") SELECT "canCallSupport", "channelId", "id", "network", "recieverId", "recieverStatus", "selectedCoin", "senderId", "senderStatus", "status" FROM "Trade";
DROP TABLE "Trade";
ALTER TABLE "new_Trade" RENAME TO "Trade";
CREATE UNIQUE INDEX "Trade_channelId_key" ON "Trade"("channelId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
