"use client";

import { useEffect, useState } from "react";

type Status = "loading" | "up" | "degraded" | "down";

type Health = {
  falkordb?: string;
  fixture_mode?: boolean;
  sources?: { dailymed?: string; openfda?: string };
};

const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function HealthDot() {
  const [status, setStatus] = useState<Status>("loading");
  const [fixture, setFixture] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${api}/api/health`)
      .then((response) => response.json())
      .then((body: Health) => {
        if (cancelled) return;
        setFixture(Boolean(body.fixture_mode));
        if (body.falkordb !== "up") {
          setStatus("down");
          return;
        }
        const degraded =
          body.sources?.dailymed === "degraded" || body.sources?.openfda === "degraded";
        setStatus(degraded ? "degraded" : "up");
      })
      .catch(() => {
        if (!cancelled) setStatus("down");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const color =
    status === "up"
      ? "#2fbf71"
      : status === "degraded"
        ? "#f08a4b"
        : status === "down"
          ? "#f0605a"
          : "#9aa3ae";
  const label =
    status === "up"
      ? "Graph up"
      : status === "degraded"
        ? "A source is degraded"
        : status === "down"
          ? "Graph down"
          : "Checking the graph";

  return (
    <div className="ml-auto flex items-center gap-3 text-sm">
      {fixture ? (
        <span className="rounded-full border border-[#43c2cb] px-2 py-0.5 text-[#43c2cb]">
          Offline snapshot of 16 Oct 2026
        </span>
      ) : null}
      <span className="inline-flex items-center gap-2 text-[#98a3b1]" title={label}>
        <span
          aria-hidden
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: color }}
        />
        <span className="sr-only">{label}</span>
        {label}
      </span>
      {status === "down" ? (
        <p className="basis-full text-[#f0605a]">
          The graph database is restarting. Try again in a minute.
        </p>
      ) : null}
    </div>
  );
}
