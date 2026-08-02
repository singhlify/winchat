import { describe, expect, it, vi } from "vitest";

import { citedIndexes, streamChat } from "@/lib/chat";

/** A fetch stub that hands back the given strings as separate network chunks. */
function mockFetchStreaming(chunks: string[]) {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });

  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(stream, { status: 200 })),
  );
}

async function collect(): Promise<unknown[]> {
  const events = [];
  for await (const event of streamChat("hi", [])) events.push(event);
  return events;
}

const SOURCES = `event: sources\ndata: {"search_query":"hi","citations":[],"reranker":"cohere","rerank_skipped_reason":null}\n\n`;
const TOKEN = (text: string) => `event: token\ndata: {"text":"${text}"}\n\n`;
const DONE = `event: done\ndata: {"model":"m","provider":"p","timings_ms":{},"candidates":{"dense":1,"lexical":2,"fused":3}}\n\n`;

describe("streamChat", () => {
  it("parses a well-formed stream in order", async () => {
    mockFetchStreaming([SOURCES, TOKEN("a"), TOKEN("b"), DONE]);

    const events = await collect();

    expect(events.map((event) => (event as { type: string }).type)).toEqual([
      "sources",
      "token",
      "token",
      "done",
    ]);
  });

  it("reassembles a frame split across network chunks", async () => {
    // The realistic failure: TCP does not respect SSE frame boundaries.
    mockFetchStreaming([`event: tok`, `en\ndata: {"te`, `xt":"split"}\n\n`]);

    const events = await collect();

    expect(events).toEqual([{ type: "token", text: "split" }]);
  });

  it("handles several frames arriving in one chunk", async () => {
    mockFetchStreaming([TOKEN("a") + TOKEN("b") + TOKEN("c")]);

    const events = await collect();

    expect(events).toHaveLength(3);
  });

  it("maps snake_case payloads onto camelCase events", async () => {
    mockFetchStreaming([SOURCES]);

    const [event] = (await collect()) as [{ searchQuery: string; rerankSkippedReason: null }];

    expect(event.searchQuery).toBe("hi");
    expect(event.rerankSkippedReason).toBeNull();
  });

  it("ignores unknown event types instead of throwing", async () => {
    mockFetchStreaming([`event: ping\ndata: {}\n\n`, TOKEN("a")]);

    const events = await collect();

    expect(events).toEqual([{ type: "token", text: "a" }]);
  });

  it("throws when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 503 })),
    );

    await expect(collect()).rejects.toThrow();
  });
});

describe("citedIndexes", () => {
  it("finds the markers the model actually wrote", () => {
    expect(citedIndexes("Apply by March 1 [2]. Fees are due later [5].")).toEqual([2, 5]);
  });

  it("deduplicates and sorts", () => {
    expect(citedIndexes("[3] and [1] and [3] again")).toEqual([1, 3]);
  });

  it("returns nothing for an uncited answer", () => {
    expect(citedIndexes("I could not find anything about that.")).toEqual([]);
  });
});
