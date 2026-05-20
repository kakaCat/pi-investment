import { Router } from "express";
import { BackupService } from "../../../services/operations/backup-service.js";
import { PlatformStatusService } from "../../../services/platform/PlatformStatusService.js";
import { requireOpsAuth } from "../middleware/ops-auth.js";

const router = Router();
const platformStatusService = new PlatformStatusService();
const backupService = new BackupService();

router.get("/status", async (_req, res, next) => {
  try {
    const status = await platformStatusService.getStatus();
    res.json({ success: true, data: status });
  } catch (error) {
    next(error);
  }
});

router.post("/backups", requireOpsAuth(), async (_req, res, next) => {
  try {
    const backup = await backupService.createBackup();
    res.status(201).json({ success: true, data: backup });
  } catch (error) {
    next(error);
  }
});

router.post("/restore-plan", requireOpsAuth(), async (req, res, next) => {
  try {
    const backupDir = typeof req.body?.backupDir === "string" ? req.body.backupDir : "";
    if (!backupDir) {
      res.status(400);
      throw new Error("backupDir is required");
    }

    const plan = await backupService.planRestore(backupDir);
    res.json({ success: true, data: plan });
  } catch (error) {
    next(error);
  }
});

router.post("/restore", requireOpsAuth(), async (req, res, next) => {
  try {
    const backupDir = typeof req.body?.backupDir === "string" ? req.body.backupDir : "";
    const confirmation = typeof req.body?.confirmation === "string" ? req.body.confirmation : "";
    if (!backupDir) {
      res.status(400);
      throw new Error("backupDir is required");
    }

    const result = await backupService.restoreBackup(backupDir, confirmation);
    res.json({ success: true, data: result });
  } catch (error) {
    next(error);
  }
});

export { router as platformRouter };
