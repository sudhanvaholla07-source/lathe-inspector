-- CreateEnum
CREATE TYPE "Role" AS ENUM ('MANAGER', 'OPERATOR');

-- CreateEnum
CREATE TYPE "InspectionResult" AS ENUM ('PASS', 'FAIL');

-- CreateEnum
CREATE TYPE "InspectionMethod" AS ENUM ('DIFF', 'YOLO');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "role" "Role" NOT NULL DEFAULT 'OPERATOR',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Machine" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "location" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Machine_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PartType" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "referenceImageUrl" TEXT NOT NULL,
    "machineId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "PartType_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Inspection" (
    "id" TEXT NOT NULL,
    "partTypeId" TEXT NOT NULL,
    "capturedImageUrl" TEXT NOT NULL,
    "diffImageUrl" TEXT,
    "method" "InspectionMethod" NOT NULL DEFAULT 'DIFF',
    "result" "InspectionResult" NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    "confirmedResult" "InspectionResult",
    "confirmedAt" TIMESTAMP(3),
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Inspection_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "PartType_machineId_idx" ON "PartType"("machineId");

-- CreateIndex
CREATE INDEX "Inspection_partTypeId_timestamp_idx" ON "Inspection"("partTypeId", "timestamp");

-- AddForeignKey
ALTER TABLE "PartType" ADD CONSTRAINT "PartType_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Inspection" ADD CONSTRAINT "Inspection_partTypeId_fkey" FOREIGN KEY ("partTypeId") REFERENCES "PartType"("id") ON DELETE CASCADE ON UPDATE CASCADE;
