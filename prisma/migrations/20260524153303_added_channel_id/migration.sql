/*
  Warnings:

  - Added the required column `channelId` to the `Trade` table without a default value. This is not possible if the table is not empty.
  - Added the required column `recieverId` to the `Trade` table without a default value. This is not possible if the table is not empty.
  - Added the required column `senderId` to the `Trade` table without a default value. This is not possible if the table is not empty.
  - Added the required column `discordId` to the `User` table without a default value. This is not possible if the table is not empty.
  - Added the required column `username` to the `User` table without a default value. This is not possible if the table is not empty.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Trade" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "channelId" INTEGER NOT NULL,
    "recieverStatus" TEXT NOT NULL DEFAULT 'WAITING',
    "senderStatus" TEXT NOT NULL DEFAULT 'WAITING',
    "senderId" INTEGER NOT NULL,
    "recieverId" INTEGER NOT NULL,
    CONSTRAINT "Trade_senderId_fkey" FOREIGN KEY ("senderId") REFERENCES "User" ("discordId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Trade_recieverId_fkey" FOREIGN KEY ("recieverId") REFERENCES "User" ("discordId") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Trade" ("id") SELECT "id" FROM "Trade";
DROP TABLE "Trade";
ALTER TABLE "new_Trade" RENAME TO "Trade";
CREATE TABLE "new_User" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "discordId" INTEGER NOT NULL,
    "username" TEXT NOT NULL
);
INSERT INTO "new_User" ("id") SELECT "id" FROM "User";
DROP TABLE "User";
ALTER TABLE "new_User" RENAME TO "User";
CREATE UNIQUE INDEX "User_discordId_key" ON "User"("discordId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
