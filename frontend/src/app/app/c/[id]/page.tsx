import type { Metadata } from "next";

import { ChatShell } from "@/components/chat/ChatShell";
import { fetchSources } from "@/lib/api/client";

/**
 * A single conversation, at its own URL.
 *
 * The transcript itself lives in the visitor's browser, so the server renders only the
 * shell and the client fills in the messages. That is the correct division here: this page
 * is private to one person and one device, and there is nothing for the server — or a
 * crawler — to render.
 */

export const metadata: Metadata = {
  title: "Chat",
  // Deliberately excluded from search. These URLs are per-device and hold nothing a
  // crawler could see anyway; indexing them would scatter empty shells across search
  // results and dilute the pages that do have content.
  robots: { index: false, follow: false },
};

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  // Route params are async in Next 16 — synchronous access was removed.
  const { id } = await params;

  let sourceCount: number | undefined;
  try {
    sourceCount = (await fetchSources({ limit: 1 })).total;
  } catch {
    // Nice to have; the chat works without it.
  }

  return <ChatShell conversationId={id} sourceCount={sourceCount} />;
}
