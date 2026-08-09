import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Covers the duplicate-conversation bug, which reached production.
 *
 * Signing in and asking one question produced TWO sidebar entries: the local conversation
 * holding the transcript, and the server's copy arriving empty. The cause is that both
 * sides legitimately mint an id — the browser needs one before the first request, for the
 * URL and for storage, and Postgres generates its own on insert — so account sync saw an
 * id it had never stored and treated a conversation it already had as new.
 *
 * The environment is "node", so `window` is stubbed rather than pulling in jsdom for two
 * tests. Only localStorage and the storage event matter here.
 */

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.resetModules();
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    },
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

const remote = (id: string, title: string) => ({
  id,
  title,
  created_at: "2026-08-09T00:00:00Z",
  updated_at: "2026-08-09T00:00:00Z",
});

describe("account sync merge", () => {
  it("does not re-add a conversation this device already created", async () => {
    const { saveConversation, mergeServerConversations, listConversations } =
      await import("@/lib/conversations");

    // Created locally while signed in: local id from the browser, serverId from the API.
    saveConversation({
      id: "local-abc",
      serverId: "server-xyz",
      title: "How much does it cost to replace my UwinCARD?",
      createdAt: 1,
      updatedAt: 2,
      turns: [{ role: "user", content: "…" }] as never,
    });

    // The same conversation comes back from the account, under the server's id.
    const added = mergeServerConversations([
      remote("server-xyz", "How much does it cost to replace my UwinCARD?"),
    ]);

    expect(added).toBe(0);
    expect(listConversations()).toHaveLength(1);
  });

  it("still adds a conversation that genuinely came from another device", async () => {
    const { saveConversation, mergeServerConversations, listConversations } =
      await import("@/lib/conversations");

    saveConversation({
      id: "local-abc",
      serverId: "server-xyz",
      title: "Mine",
      createdAt: 1,
      updatedAt: 2,
      turns: [] as never,
    });

    const added = mergeServerConversations([
      remote("server-from-phone", "Asked on my phone"),
    ]);

    expect(added).toBe(1);
    expect(listConversations().map((c) => c.id)).toContain("server-from-phone");
  });

  it("is idempotent — syncing twice does not duplicate", async () => {
    const { mergeServerConversations, listConversations } =
      await import("@/lib/conversations");

    mergeServerConversations([remote("server-1", "One")]);
    mergeServerConversations([remote("server-1", "One")]);

    expect(listConversations()).toHaveLength(1);
  });
});
