import type { NextFunction, Request, Response } from "express";

export function requireOpsAuth(configuredToken?: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const expectedToken = configuredToken ?? process.env.OPS_API_TOKEN;
    if (!expectedToken) {
      next();
      return;
    }

    if (extractToken(req) === expectedToken) {
      next();
      return;
    }

    res.status(401).json({
      success: false,
      error: "Missing or invalid operations token",
    });
  };
}

function extractToken(req: Request): string | undefined {
  const headerToken = req.header("x-pi-ops-token");
  if (headerToken) {
    return headerToken;
  }

  const authorization = req.header("authorization");
  const match = authorization?.match(/^Bearer\s+(.+)$/i);
  return match?.[1];
}
