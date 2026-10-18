"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

const examples = ["68071-3355-9", "63187-626-30", "42291-622-30", "31722-726-90", "16729-119-15"];

export default function HomePage() {
  const router = useRouter();
  const [ndc, setNdc] = useState("");
  const [strict, setStrict] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = ndc.trim();
    if (!value) return;
    router.push(`/ndc/${encodeURIComponent(value)}?strict=${strict ? "1" : "0"}`);
  }

  return (
    <section className="max-w-3xl">
      <h1 className="text-4xl font-semibold tracking-tight">Did the warning land?</h1>
      <p className="mt-3 text-[#98a3b1]">
        Type the NDC printed on a drug label. Landfall follows the real chain from FDA&apos;s
        labeling change to the label of record for that NDC in FalkorDB, and tells you whether the
        boxed warning is there and who can fix it if not.
      </p>
      <form onSubmit={submit} className="mt-6 flex flex-col gap-3 rounded-xl bg-[#161d25] p-4">
        <label className="text-sm text-[#98a3b1]" htmlFor="ndc">
          NDC
        </label>
        <input
          id="ndc"
          name="ndc"
          value={ndc}
          onChange={(event) => setNdc(event.target.value)}
          placeholder="68071-3355-9"
          className="mono rounded-lg border border-white/10 bg-[#0f1419] px-3 py-2 text-[#e6ebf0] outline-none focus:border-[#43c2cb]"
        />
        <div className="flex flex-wrap gap-2">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              className="mono rounded-full border border-white/10 px-2 py-1 text-xs text-[#98a3b1] hover:border-[#43c2cb]"
              onClick={() => setNdc(example)}
            >
              {example}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-[#98a3b1]">
          <input
            type="checkbox"
            checked={strict}
            onChange={(event) => setStrict(event.target.checked)}
          />
          Strict mode (only pharmacist-confirmed absences)
        </label>
        <button
          type="submit"
          className="w-fit rounded-lg bg-[#43c2cb] px-4 py-2 font-medium text-[#0f1419]"
        >
          Check
        </button>
      </form>
    </section>
  );
}
