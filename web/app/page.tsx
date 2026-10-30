import { Thread } from "@/components/Thread";
import { MAX_LENGTHS } from "@/lib/api/limits";
import { TAGLINE, WORDMARK } from "@/lib/wording";

export default function Home() {
  return (
    <main>
      <Thread
        masthead={
          <header className="grid gap-1.5">
            <h1 className="display-wide text-[1.375rem] leading-none font-extrabold tracking-[-0.01em] lowercase lg:text-[1.625rem]">
              {WORDMARK}
            </h1>
            <p className="text-sm leading-tight lg:text-base">{TAGLINE}</p>
          </header>
        }
        maxLengths={MAX_LENGTHS}
      />
    </main>
  );
}
