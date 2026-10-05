"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { DataClassBadge } from "@/components/Badges";
import { ProvenanceButton } from "@/components/Provenance";
import { apiSend } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { AssistantAnswer } from "@/lib/types";

const EXAMPLES = [
  "¿Qué está pasando actualmente en la comuna?",
  "¿Hay escuelas en zonas de riesgo?",
  "¿Qué sectores deberíamos revisar primero?",
  "¿Qué sectores se han inundado históricamente?",
  "¿Qué dice el plan de emergencia sobre albergues?",
  "¿Ha aumentado la cantidad de sismos?",
];

type Audience = "ejecutivo" | "tecnico" | "vecino";
const AUDIENCES: { key: Audience; label: string }[] = [
  { key: "ejecutivo", label: "Resumen ejecutivo" },
  { key: "tecnico", label: "Detalle técnico" },
  { key: "vecino", label: "Como a un vecino" },
];

interface Turn {
  question: string;
  audience: Audience;
  answer?: AssistantAnswer;
  error?: string;
}

function renderAnswer(text: string) {
  const lines = text.split("\n").filter((l) => l.trim());
  return lines.map((line, i) => {
    const bullet = line.trim().startsWith("- ");
    const content = (bullet ? line.trim().slice(2) : line).split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
      part.startsWith("**") && part.endsWith("**") ? <strong key={j}>{part.slice(2, -2)}</strong> : <span key={j}>{part}</span>,
    );
    return bullet ? (
      <p key={i} className="ml-4 list-item list-disc text-sm">
        {content}
      </p>
    ) : (
      <p key={i} className="mt-2 text-sm first:mt-0">
        {content}
      </p>
    );
  });
}

export function AssistantPanel() {
  const [question, setQuestion] = useState("");
  const [audience, setAudience] = useState<Audience>("ejecutivo");
  const [turns, setTurns] = useState<Turn[]>([]);
  const ask = useMutation({
    mutationFn: (t: Turn) => apiSend<AssistantAnswer>("/assistant", "POST", { question: t.question, audience: t.audience }),
  });

  function submit(text: string) {
    const q = text.trim();
    if (!q) return;
    const turn: Turn = { question: q, audience };
    setTurns((prev) => [...prev, turn]);
    setQuestion("");
    ask.mutate(turn, {
      onSuccess: (answer) => setTurns((prev) => prev.map((t) => (t === turn ? { ...t, answer } : t))),
      onError: (e) => setTurns((prev) => prev.map((t) => (t === turn ? { ...t, error: (e as Error).message } : t))),
    });
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-base font-semibold">Asistente</h3>
        <p className="mt-0.5 text-sm text-muted">Responde sólo con los datos de la plataforma y cita sus fuentes. No emite alertas ni toma decisiones.</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {AUDIENCES.map((a) => (
            <button
              key={a.key}
              onClick={() => setAudience(a.key)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${audience === a.key ? "border-brand bg-brand text-white" : "border-border hover:bg-slate-50"}`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 space-y-3">
        {turns.length === 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {EXAMPLES.map((e) => (
              <button key={e} onClick={() => submit(e)} className="rounded-xl border border-border bg-surface p-3 text-left text-sm hover:border-brand">
                {e}
              </button>
            ))}
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-brand px-3.5 py-2 text-sm text-white">{t.question}</div>
            <div className="rounded-2xl rounded-bl-sm border border-border bg-surface p-4 shadow-sm">
              {!t.answer && !t.error && <p className="text-sm text-muted">Consultando los datos...</p>}
              {t.error && <p className="text-sm text-red-700">{t.error}</p>}
              {t.answer && (
                <>
                  {t.answer.notice && <p className="mb-2 rounded-lg bg-amber-50 px-2 py-1 text-xs text-amber-900">{t.answer.notice}</p>}
                  <div>{renderAnswer(t.answer.answer)}</div>
                  {t.answer.sources.length > 0 && (
                    <div className="mt-3 border-t border-border pt-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Fuentes</p>
                      <ul className="mt-1 space-y-1">
                        {t.answer.sources.map((s, j) => (
                          <li key={j} className="flex flex-wrap items-center gap-2 text-xs">
                            <DataClassBadge dataClass={s.data_class} />
                            <span>{s.source}</span>
                            {s.updated_at && <span className="text-muted">{formatTime(s.updated_at)}</span>}
                            <ProvenanceButton id={s.provenance_id} label="origen" />
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <p className="mt-2 text-[11px] text-muted">{t.answer.disclaimer}</p>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
        className="sticky bottom-0 flex gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Escriba su pregunta"
          maxLength={1000}
          className="flex-1 rounded-lg px-3 py-2 text-sm outline-none"
        />
        <button disabled={ask.isPending || !question.trim()} className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          Preguntar
        </button>
      </form>
    </div>
  );
}
