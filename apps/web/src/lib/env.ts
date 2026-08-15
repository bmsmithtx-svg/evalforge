import { z } from "zod";

/**
 * Server-side environment configuration.
 *
 * Validated once at module load so a missing or malformed value fails
 * immediately with a clear error instead of surfacing as an obscure
 * runtime failure deep in a request handler.
 */
const EnvSchema = z.object({
  API_BASE_URL: z.string().url(),
});

export type Env = z.infer<typeof EnvSchema>;

export function loadEnv(): Env {
  const parsed = EnvSchema.safeParse({
    API_BASE_URL: process.env.API_BASE_URL,
  });

  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
      .join("; ");
    throw new Error(`Invalid frontend environment configuration: ${issues}`);
  }

  return parsed.data;
}

export const env = loadEnv();
