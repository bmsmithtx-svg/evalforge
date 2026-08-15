// Baseline environment for modules that validate configuration at import time.
// Individual tests may override this with vi.stubEnv / vi.unstubAllEnvs.
process.env.API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";
