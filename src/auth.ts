import type { Request, Response, NextFunction } from "express";

/**
 * Express middleware enforcing a static bearer token. Constant-time comparison
 * to avoid timing attacks.
 */
export function bearerAuth(expectedToken: string) {
  const expected = Buffer.from(expectedToken, "utf8");
  return (req: Request, res: Response, next: NextFunction): void => {
    const header = req.header("authorization");
    if (!header || !header.toLowerCase().startsWith("bearer ")) {
      unauthorized(res);
      return;
    }
    const provided = Buffer.from(header.slice(7).trim(), "utf8");
    if (provided.length !== expected.length) {
      unauthorized(res);
      return;
    }
    let diff = 0;
    for (let i = 0; i < expected.length; i++) {
      diff |= expected[i]! ^ provided[i]!;
    }
    if (diff !== 0) {
      unauthorized(res);
      return;
    }
    next();
  };
}

function unauthorized(res: Response): void {
  res.setHeader("WWW-Authenticate", 'Bearer realm="tebex-mcp"');
  res.status(401).json({
    jsonrpc: "2.0",
    error: { code: -32001, message: "Unauthorized" },
    id: null,
  });
}
