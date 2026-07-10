// JWT auth: reads the token from "Authorization: Bearer <token>", verifies
// its signature against JWT_SECRET, and attaches the decoded payload
// (id, role) to req.user. No database lookup needed -- that's the whole
// point of a signed token: the server can trust it just by checking the
// signature, instead of querying the DB on every single request.
const jwt = require("jsonwebtoken");

function requireAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const [scheme, token] = header.split(" ");

  if (scheme !== "Bearer" || !token) {
    return res.status(401).json({ error: "Missing or malformed Authorization header" });
  }

  try {
    req.user = jwt.verify(token, process.env.JWT_SECRET);
    next();
  } catch (err) {
    return res.status(401).json({ error: "Invalid or expired token" });
  }
}

// Restricts a route to specific roles, e.g. requireRole("MANAGER").
// Must run after requireAuth so req.user is already populated.
function requireRole(...roles) {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return res.status(403).json({ error: "Insufficient permissions" });
    }
    next();
  };
}

module.exports = { requireAuth, requireRole };
