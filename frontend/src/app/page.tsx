import { Chat } from "@/components/chat/Chat";
import { fetchSources } from "@/lib/api/client";

/**
 * The chat page.
 *
 * The source count is fetched on the server so the first paint states the assistant's real
 * scope ("556 articles") rather than a placeholder that pops in later.
 */
export const revalidate = 3600;

export default async function Home() {
  let sourceCount: number | undefined;
  try {
    sourceCount = (await fetchSources({ limit: 1 })).total;
  } catch {
    // A number is nice to have; the chat works without it.
  }

  return (
    <div id="main">
      <Chat sourceCount={sourceCount} />
    </div>
  );
}
