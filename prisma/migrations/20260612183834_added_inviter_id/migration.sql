-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Invite" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "targetId" TEXT NOT NULL,
    "senderId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Invite_targetId_fkey" FOREIGN KEY ("targetId") REFERENCES "User" ("discordId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Invite_senderId_fkey" FOREIGN KEY ("senderId") REFERENCES "User" ("discordId") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Invite" ("createdAt", "id", "status", "targetId") SELECT "createdAt", "id", "status", "targetId" FROM "Invite";
DROP TABLE "Invite";
ALTER TABLE "new_Invite" RENAME TO "Invite";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
