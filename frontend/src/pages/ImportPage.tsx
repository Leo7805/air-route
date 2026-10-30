import { useRef, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api } from "../lib/api";
import type { ImportResponse } from "../types/api";

const datasets = [
  {
    key: "airports",
    label: "Airports CSV",
    description: "Airport records and location details.",
  },
  {
    key: "airlines",
    label: "Airlines CSV",
    description: "Airline records and codes.",
  },
  {
    key: "routes",
    label: "Routes CSV",
    description: "Route records and their references.",
  },
] as const;

type DatasetKey = (typeof datasets)[number]["key"];

function errorMessage(reason: unknown) {
  return reason instanceof ApiError
    ? reason.message
    : "Unable to import the selected data.";
}

export function ImportPage() {
  const { token } = useAuth();
  const inputRefs = useRef<Record<DatasetKey, HTMLInputElement | null>>({
    airports: null,
    airlines: null,
    routes: null,
  });
  const [files, setFiles] = useState<Partial<Record<DatasetKey, File>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [result, setResult] = useState<ImportResponse | null>(null);

  function chooseFile(dataset: DatasetKey, fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    setFiles((current) => ({ ...current, [dataset]: file }));
    setFeedback(null);
    setResult(null);
  }

  function clearFile(dataset: DatasetKey) {
    setFiles((current) => {
      const next = { ...current };
      delete next[dataset];
      return next;
    });
    const input = inputRefs.current[dataset];
    if (input) input.value = "";
    setFeedback(null);
    setResult(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || Object.keys(files).length === 0) {
      setFeedback({ type: "error", message: "Select at least one CSV file." });
      return;
    }
    if (
      !window.confirm(
        "Import the selected datasets? Each selected dataset replaces its existing records. Unselected datasets remain unchanged.",
      )
    ) {
      return;
    }

    setFeedback(null);
    setResult(null);
    setIsSubmitting(true);
    try {
      const response = await api.importDatasets(token, files);
      setResult(response);
      setFeedback({ type: "success", message: response.message });
      setFiles({});
      for (const dataset of datasets) {
        const input = inputRefs.current[dataset.key];
        if (input) input.value = "";
      }
    } catch (reason) {
      setFeedback({ type: "error", message: errorMessage(reason) });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="import-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Data Import</span>
          <h1>Refresh aviation data.</h1>
          <p>Upload one or more validated CSV datasets for the Explorer.</p>
        </div>
      </div>

      <div className="import-warning">
        <strong>Replacement behaviour</strong>
        <span>
          Each selected dataset replaces the existing records for that dataset.
          Files you do not select are left unchanged. Imports are atomic, so a
          validation or Travel Plan route conflict rejects the whole request.
        </span>
      </div>

      {feedback && (
        <p
          className={`feedback feedback-${feedback.type}`}
          role={feedback.type === "error" ? "alert" : "status"}
        >
          {feedback.message}
        </p>
      )}

      <form className="import-form" onSubmit={handleSubmit}>
        <div className="import-file-grid">
          {datasets.map((dataset) => {
            const file = files[dataset.key];
            return (
              <div className="import-file-card" key={dataset.key}>
                <div>
                  <span className="eyebrow">{dataset.key}</span>
                  <h2>{dataset.label}</h2>
                  <p>{dataset.description}</p>
                </div>
                <input
                  accept=".csv,text/csv"
                  className="file-input"
                  onChange={(event) =>
                    chooseFile(dataset.key, event.target.files)
                  }
                  ref={(input) => {
                    inputRefs.current[dataset.key] = input;
                  }}
                  type="file"
                />
                <div className="file-actions">
                  <button
                    className="button button-quiet"
                    disabled={isSubmitting}
                    onClick={() => inputRefs.current[dataset.key]?.click()}
                    type="button"
                  >
                    {file ? "Change file" : "Choose CSV"}
                  </button>
                  {file && (
                    <>
                      <span className="file-name">{file.name}</span>
                      <button
                        className="text-button text-button-danger"
                        disabled={isSubmitting}
                        onClick={() => clearFile(dataset.key)}
                        type="button"
                      >
                        Remove
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="import-actions">
          <span>
            {Object.keys(files).length} of {datasets.length} datasets selected
          </span>
          <button
            className="button button-primary"
            disabled={isSubmitting || Object.keys(files).length === 0}
            type="submit"
          >
            {isSubmitting ? "Importing…" : "Import selected datasets"}
          </button>
        </div>
      </form>

      {result && (
        <section className="panel import-result">
          <span className="eyebrow">Import summary</span>
          <h2>Data is ready in Aviation Explorer.</h2>
          <div className="import-counts">
            {result.datasets.map((dataset) => (
              <div key={dataset}>
                <strong>{result.counts[dataset as DatasetKey]}</strong>
                <span>{dataset}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
