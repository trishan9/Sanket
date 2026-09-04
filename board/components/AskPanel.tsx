"use client";

import { useState } from "react";
import { askSandbox } from "@/lib/api";
import { t, useLang } from "@/lib/i18n";

export function AskPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{ answer: string; code: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const lang = useLang((s) => s.lang);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setAnswer(null);
    const result = await askSandbox(question);
    setAnswer(result);
    setLoading(false);
  };

  return (
    <section className="mt-4 card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        {t("ask", lang)}
      </h2>
      <p className="mt-1 text-[10px] text-ink-faint">
        Read-only analyst sandbox, no writes, no network, 10 s timeout, results tagged
        model_output.
      </p>
      <form onSubmit={submit} className="mt-2 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. which settlements have under 20 minutes in every scenario?"
          className="flex-1 rounded border border-line bg-surface px-3 py-2 text-sm"
        />
        <button
          disabled={loading}
          className="rounded bg-accent px-3 py-2 text-sm font-medium disabled:opacity-50"
        >
          {loading ? "…" : "Ask"}
        </button>
      </form>
      {answer ? (
        <div className="mt-3">
          <p className="text-sm">{answer.answer}</p>
          <pre className="mt-2 overflow-x-auto rounded bg-surface p-2 text-[10px] text-ink-muted">
            {answer.code}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
