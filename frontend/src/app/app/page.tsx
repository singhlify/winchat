import { ChatShell } from "@/components/chat/ChatShell";

/**
 * The chat page. The source count is fetched on the server so the first paint states the
 * assistant's real scope ("556 articles") rather than a placeholder that pops in later.
 */
export const revalidate = 3600;

export default async function Home() {
  return <ChatShell />;
}
