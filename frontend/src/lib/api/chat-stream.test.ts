import { describe, expect, it, vi } from "vitest";

import { citedIndexes, streamChat } from "@/lib/api/chat-stream";

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

const SOURCES =
  `event: sources\ndata: {"search_query":"hi","citations":[],"reranker":"cohere",` +
  `"rerank_skipped_reason":null,"refused":false,"refusal":null,"near_misses":[]}\n\n`;
const TOKEN = (text: string) => `event: token\ndata: {"text":"${text}"}\n\n`;
const DONE =
  `event: done\ndata: {"model":"m","provider":"p","conversation_id":null,` +
  `"timings_ms":{},"candidates":{"dense":1,"lexical":2,"fused":3}}\n\n`;

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

    expect(await collect()).toEqual([{ type: "token", text: "split" }]);
  });

  it("handles several frames arriving in one chunk", async () => {
    mockFetchStreaming([TOKEN("a") + TOKEN("b") + TOKEN("c")]);

    expect(await collect()).toHaveLength(3);
  });

  it("ignores unknown event types instead of throwing", async () => {
    // Forward compatibility: a new server-side event must not break an older client.
    mockFetchStreaming([`event: ping\ndata: {}\n\n`, TOKEN("a")]);

    expect(await collect()).toEqual([{ type: "token", text: "a" }]);
  });

  it("rejects a payload that does not match the schema", async () => {
    // A renamed or missing field must fail loudly here, not render as undefined later.
    mockFetchStreaming([`event: sources\ndata: {"citations":"not-an-array"}\n\n`]);

    await expect(collect()).rejects.toThrow();
  });

  it("rejects a citation whose url is not a url", async () => {
    // This value becomes an href; a non-URL there is an injection vector, not a typo.
    mockFetchStreaming([
      `event: sources\ndata: {"search_query":"q","citations":[{"index":1,"a_id":"1",` +
        `"question":"Q","url":"javascript:alert(1)","score":0.5}],"reranker":"none",` +
        `"rerank_skipped_reason":null,"refused":false,"refusal":null,"near_misses":[]}\n\n`,
    ]);

    await expect(collect()).rejects.toThrow();
  });

  it("surfaces a rate limit with its retry hint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Rate limit reached." }), {
            status: 429,
            headers: { "retry-after": "600" },
          }),
      ),
    );

    await expect(collect()).rejects.toMatchObject({
      status: 429,
      retryAfterSeconds: 600,
    });
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
