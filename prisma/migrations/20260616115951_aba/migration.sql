-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Trade" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "channelId" TEXT,
    "recieverStatus" TEXT NOT NULL DEFAULT 'WAITING',
    "senderStatus" TEXT NOT NULL DEFAULT 'WAITING',
    "status" TEXT NOT NULL DEFAULT 'WAITING',
    "selectedCoin" TEXT NOT NULL,
    "network" TEXT NOT NULL,
    "calledSupport" BOOLEAN NOT NULL DEFAULT false,
    "received" TEXT,
    "hideSender" BOOLEAN NOT NULL DEFAULT false,
    "hideReciever" BOOLEAN NOT NULL DEFAULT false,
    "senderId" TEXT,
    "recieverId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "membersId" TEXT,
    CONSTRAINT "Trade_senderId_fkey" FOREIGN KEY ("senderId") REFERENCES "User" ("discordId") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Trade_recieverId_fkey" FOREIGN KEY ("recieverId") REFERENCES "User" ("discordId") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Trade" ("calledSupport", "channelId", "createdAt", "hideReciever", "hideSender", "id", "membersId", "network", "received", "recieverId", "recieverStatus", "selectedCoin", "senderId", "senderStatus", "status") SELECT "calledSupport", "channelId", "createdAt", "hideReciever", "hideSender", "id", "membersId", "network", "received", "recieverId", "recieverStatus", "selectedCoin", "senderId", "senderStatus", "status" FROM "Trade";
DROP TABLE "Trade";
ALTER TABLE "new_Trade" RENAME TO "Trade";
CREATE UNIQUE INDEX "Trade_channelId_key" ON "Trade"("channelId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
