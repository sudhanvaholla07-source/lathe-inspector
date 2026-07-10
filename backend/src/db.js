// Single shared Prisma Client instance. Importing this file anywhere in the
// app reuses the same DB connection pool instead of opening a new one per
// request -- opening a fresh client per request is a common beginner mistake
// that exhausts Postgres's connection limit under load.
const { PrismaClient } = require("@prisma/client");

const prisma = new PrismaClient();

module.exports = prisma;
