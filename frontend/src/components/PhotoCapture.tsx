import { useRef, useState } from "react";

interface Props {
  label: string;
  onSubmit: (file: File) => Promise<void>;
  submitLabel?: string;
  hint?: string;
}

/** Camera-first image picker (opens the rear camera on mobile) with preview. */
export function PhotoCapture({ label, onSubmit, submitLabel = "Upload", hint }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pick = (f: File | null) => {
    setFile(f);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  return (
    <div className="capture">
      <label className="field-label">{label}</label>
      {hint && <p className="muted small">{hint}</p>}
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => pick(e.target.files?.[0] ?? null)}
      />
      {preview ? (
        <img src={preview} alt="Preview" className="capture-preview" />
      ) : (
        <button type="button" className="capture-drop" onClick={() => input.current?.click()}>
          📷 Tap to take a photo
        </button>
      )}
      <div className="row gap">
        {preview && (
          <button type="button" className="btn btn-ghost" onClick={() => input.current?.click()}>
            Retake
          </button>
        )}
        <button
          type="button"
          className="btn"
          disabled={!file || busy}
          onClick={async () => {
            if (!file) return;
            setBusy(true);
            try {
              await onSubmit(file);
              pick(null);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Uploading…" : submitLabel}
        </button>
      </div>
    </div>
  );
}
