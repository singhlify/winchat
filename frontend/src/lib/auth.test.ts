import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * These cover the two auth behaviours that are security decisions rather than UI choices.
 * The happy paths are supabase-js's job and testing them would only assert that a mock was
 * called.
 */

const auth = {
  resetPasswordForEmail: vi.fn(),
  signInWithOAuth: vi.fn(),
  signInWithPassword: vi.fn(),
};

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({ auth }),
  authRedirectTo: (path: string) => `https://winchat.test${path}`,
  authConfigured: true,
}));

beforeEach(() => {
  vi.clearAllMocks();
  auth.resetPasswordForEmail.mockResolvedValue({ error: null });
  auth.signInWithOAuth.mockResolvedValue({ error: null });
  auth.signInWithPassword.mockResolvedValue({ error: null });
});

describe("password reset", () => {
  it("says the same thing whether or not the account exists", async () => {
    // A reset form that distinguishes the two cases is a membership oracle: an attacker
    // can farm which addresses are registered without ever signing in. The wording must
    // stay conditional ("if that email has an account") for that reason, not for politeness.
    const { sendPasswordReset } = await import("@/lib/auth");

    const known = await sendPasswordReset("real@uwindsor.ca");
    auth.resetPasswordForEmail.mockResolvedValueOnce({ error: null });
    const unknown = await sendPasswordReset("nobody@uwindsor.ca");

    expect(known.notice).toBe(unknown.notice);
    expect(known.notice).toMatch(/if that email has an account/i);
    expect(known.error).toBeNull();
  });

  it("sends the reset link to this origin's reset page", async () => {
    const { sendPasswordReset } = await import("@/lib/auth");

    await sendPasswordReset("someone@uwindsor.ca");

    expect(auth.resetPasswordForEmail).toHaveBeenCalledWith(
      "someone@uwindsor.ca",
      expect.objectContaining({
        redirectTo: "https://winchat.test/auth/reset",
      }),
    );
  });
});

describe("error messages", () => {
  it("translates the credential failure without revealing which half was wrong", async () => {
    // "No account with that email" would leak registration status just as the reset form
    // would. Supabase returns one message for both; this asserts we keep it that way.
    auth.signInWithPassword.mockResolvedValueOnce({
      error: { message: "Invalid login credentials" },
    });
    const { signInWithPassword } = await import("@/lib/auth");

    const result = await signInWithPassword("a@b.test", "wrong");

    expect(result.error).toMatch(/do not match an account/i);
    expect(result.error).not.toMatch(
      /password is wrong|no such user|not registered/i,
    );
  });

  it("passes an unrecognised message through rather than inventing one", async () => {
    auth.signInWithPassword.mockResolvedValueOnce({
      error: { message: "Signups not allowed for this instance" },
    });
    const { signInWithPassword } = await import("@/lib/auth");

    const result = await signInWithPassword("a@b.test", "pw");

    expect(result.error).toBe("Signups not allowed for this instance");
  });
});

describe("oauth", () => {
  it("returns to this origin's callback route", async () => {
    const { signInWithProvider } = await import("@/lib/auth");

    await signInWithProvider("google");

    expect(auth.signInWithOAuth).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: "google",
        options: expect.objectContaining({
          redirectTo: "https://winchat.test/auth/callback",
        }),
      }),
    );
  });
});
