import type { Metadata } from "next";

import { ChatShell } from "@/components/chat/ChatShell";

/**
 * A single conversation, at its own URL. The transcript itself lives in the visitor's
 * browser, so the server renders only the shell and the client fills in the messages.
 */

export const metadata: Metadata = {
  title: "Chat",
  // Deliberately excluded from search. These URLs are per-device and hold nothing a crawler
  // could see anyway; indexing them would scatter empty shells across search results and
  // dilute the pages that do have content.
  robots: { index: false, follow: false },
};

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  // Route params are async in Next 16. Synchronous access was removed.
  const { id } = await params;

  return <ChatShell conversationId={id} />;
}
