import Shell from "@/components/layout/Shell";

/**
 * Application shell scope. Everything under this route group is wrapped in the
 * authenticated Shell (sidebar + topbar + auth gate). Kept out of the root
 * layout so sibling routes — e.g. the Shell-free `/preview` design showcase —
 * can render against the same tokens, watermark and cursor-glow without the
 * login gate.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <Shell>{children}</Shell>;
}
